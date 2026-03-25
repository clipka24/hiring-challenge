"""
AB Test analysis logic.

Winner criterion:
  A variant wins if its CTR is at least 20% HIGHER than the CTR of every
  other variant.

  Mathematically:
      winner_ctr >= other_ctr * 1.20   for ALL other variants

  If no single variant satisfies this condition, the result is None ("no winner yet").
"""

import json
import logging

logger = logging.getLogger(__name__)

# Minimum relative CTR advantage required to declare a winner (20 %)
WINNER_CTR_THRESHOLD = 1.20


def parse_sns_message(record: dict) -> dict:
    """
    Extract and validate the JSON payload from an SNS record.

    Raises:
        ValueError: if the record structure is invalid or required fields are missing.
    """
    try:
        sns_body = record["Sns"]["Message"]
    except KeyError as exc:
        raise ValueError(f"Malformed SNS record – missing key: {exc}") from exc

    try:
        payload = json.loads(sns_body)
    except json.JSONDecodeError as exc:
        raise ValueError(f"SNS message body is not valid JSON: {exc}") from exc

    _validate_payload(payload)
    return payload


def _validate_payload(payload: dict) -> None:
    """Raise ValueError if mandatory fields are absent or structurally wrong."""

    required_top_level = ("test_id", "variants")
    for field in required_top_level:
        if field not in payload:
            raise ValueError(f"Missing required field: '{field}'")

    variants = payload["variants"]
    if not isinstance(variants, list) or len(variants) < 2:
        raise ValueError("'variants' must be a list with at least two entries")

    for idx, variant in enumerate(variants):
        if "id" not in variant:
            raise ValueError(f"Variant at index {idx} is missing 'id'")
        if "views" not in variant or "clicks" not in variant:
            raise ValueError(
                f"Variant '{variant.get('id', idx)}' is missing 'views' or 'clicks'"
            )
        views = int(variant["views"])
        clicks = int(variant["clicks"])
        if views < 0 or clicks < 0:
            raise ValueError(
                f"Variant '{variant['id']}' has negative views or clicks"
            )
        if clicks > views:
            raise ValueError(
                f"Variant '{variant['id']}' has more clicks than views"
            )


def compute_ctr(views, clicks) -> float:
    """Return CTR as a float (0.0 if no views)."""
    views, clicks = int(views), int(clicks)
    return clicks / views if views > 0 else 0.0


def _compute_ctrs(variants: list[dict]) -> dict:
    """Return a mapping of variant id → CTR (0.0 if no views)."""
    return {v["id"]: compute_ctr(v["views"], v["clicks"]) for v in variants}


def determine_winner(variants: list[dict]) -> int | None:
    """
    Evaluate variants and return the winner's id, or None if no winner yet.

    A variant is declared the winner only if its CTR is at least 20% higher
    than the CTR of EVERY other variant.
    """
    ctrs = _compute_ctrs(variants)

    logger.info("Computed CTRs: %s", {k: f"{v:.4f}" for k, v in ctrs.items()})

    for candidate, candidate_ctr in ctrs.items():
        others = {vid: ctr for vid, ctr in ctrs.items() if vid != candidate}

        if candidate_ctr == 0.0:
            # A variant with zero CTR can never be a winner
            continue

        if all(
                candidate_ctr >= other_ctr * WINNER_CTR_THRESHOLD
                for other_ctr in others.values()
        ):
            logger.info(
                "Winner found: '%s' with CTR %.4f (threshold factor: %.2f)",
                candidate,
                candidate_ctr,
                WINNER_CTR_THRESHOLD,
            )
            return candidate

    logger.info(
        "No winner determined. No variant exceeds the %.0f%% CTR advantage threshold.",
        (WINNER_CTR_THRESHOLD - 1) * 100,
        )
    return None