"""Unit tests for the AB test analyzer logic."""

import json

import pytest

from analyzer import compute_ctr, determine_winner, parse_sns_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_record(payload: dict) -> dict:
    return {"Sns": {"Message": json.dumps(payload)}}


def make_payload(variants: list[dict], test_id: str = "test-1") -> dict:
    return {"test_id": test_id, "content_id": "test-content", "variants": variants}


# ---------------------------------------------------------------------------
# parse_sns_message
# ---------------------------------------------------------------------------

class TestParseSnsMessage:
    def test_valid_payload(self):
        payload = make_payload([
            {"id": 0, "views": "1000", "clicks": "100"},
            {"id": 1, "views": "1000", "clicks": "80"},
        ])
        result = parse_sns_message(make_record(payload))
        assert result["test_id"] == "test-1"

    def test_missing_sns_key(self):
        with pytest.raises(ValueError, match="Malformed SNS record"):
            parse_sns_message({"NotSns": {}})

    def test_invalid_json(self):
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_sns_message({"Sns": {"Message": "not-json"}})

    def test_missing_test_id(self):
        payload = {"variants": [
            {"id": 0, "views": "100", "clicks": "10"},
            {"id": 1, "views": "100", "clicks": "8"},
        ]}
        with pytest.raises(ValueError, match="test_id"):
            parse_sns_message(make_record(payload))

    def test_only_one_variant(self):
        payload = make_payload([{"id": 0, "views": "100", "clicks": "10"}])
        with pytest.raises(ValueError, match="at least two"):
            parse_sns_message(make_record(payload))

    def test_clicks_exceed_impressions(self):
        payload = make_payload([
            {"id": 0, "views": "50", "clicks": "100"},
            {"id": 1, "views": "100", "clicks": "10"},
        ])
        with pytest.raises(ValueError, match="more clicks than views"):
            parse_sns_message(make_record(payload))

    def test_negative_impressions(self):
        payload = make_payload([
            {"id": 0, "views": "-10", "clicks": "5"},
            {"id": 1, "views": "100", "clicks": "10"},
        ])
        with pytest.raises(ValueError, match="negative views or clicks"):
            parse_sns_message(make_record(payload))

    def test_wire_format_integer_ids_and_string_values(self):
        # Matches the actual SNS payload format: integer ids, string clicks/views
        payload = make_payload([
            {"id": 0, "views": "5464", "clicks": "120"},
            {"id": 1, "views": "5470", "clicks": "160"},
        ])
        result = parse_sns_message(make_record(payload))
        assert result["variants"][0]["id"] == 0
        assert result["variants"][1]["id"] == 1


# ---------------------------------------------------------------------------
# compute_ctr
# ---------------------------------------------------------------------------

class TestComputeCtr:
    def test_normal(self):
        assert compute_ctr(1000, 200) == pytest.approx(0.2)

    def test_string_inputs(self):
        assert compute_ctr("1000", "200") == pytest.approx(0.2)

    def test_zero_views(self):
        assert compute_ctr(0, 0) == 0.0

    def test_zero_clicks(self):
        assert compute_ctr(1000, 0) == 0.0


# ---------------------------------------------------------------------------
# determine_winner  – exact boundary tests
# ---------------------------------------------------------------------------

class TestDetermineWinner:
    def _variants(self, a_clicks, b_clicks, views=1000):
        return [
            {"id": 0, "views": views, "clicks": a_clicks},
            {"id": 1, "views": views, "clicks": b_clicks},
        ]

    def test_clear_winner_a(self):
        # id=0 CTR = 0.240, id=1 CTR = 0.100 → 0.240 / 0.100 = 2.4 ≥ 1.20
        variants = self._variants(240, 100)
        assert determine_winner(variants) == 0

    def test_clear_winner_b(self):
        variants = self._variants(100, 240)
        assert determine_winner(variants) == 1

    def test_exactly_20_percent_advantage(self):
        # id=0 CTR = 0.120, id=1 CTR = 0.100 → ratio exactly 1.20 → winner
        variants = self._variants(120, 100)
        assert determine_winner(variants) == 0

    def test_just_below_threshold_no_winner(self):
        # id=0 CTR = 0.1199, id=1 CTR = 0.100 → ratio < 1.20 → no winner
        variants = [
            {"id": 0, "views": 10000, "clicks": 1199},
            {"id": 1, "views": 10000, "clicks": 1000},
        ]
        assert determine_winner(variants) is None

    def test_equal_ctr_no_winner(self):
        variants = self._variants(100, 100)
        assert determine_winner(variants) is None

    def test_all_zero_impressions(self):
        variants = [
            {"id": 0, "views": 0, "clicks": 0},
            {"id": 1, "views": 0, "clicks": 0},
        ]
        assert determine_winner(variants) is None

    def test_one_variant_zero_impressions(self):
        # id=0 has real data, id=1 has none → id=0 CTR / id=1 CTR comparison
        # id=1 CTR = 0 → id=0 would need to be ≥ 0 * 1.20 = 0, always true if id=0 > 0
        variants = [
            {"id": 0, "views": 1000, "clicks": 100},
            {"id": 1, "views": 0, "clicks": 0},
        ]
        assert determine_winner(variants) == 0

    def test_three_variants_one_winner(self):
        variants = [
            {"id": 0, "views": 1000, "clicks": 300},  # CTR 0.30
            {"id": 1, "views": 1000, "clicks": 100},  # CTR 0.10
            {"id": 2, "views": 1000, "clicks": 120},  # CTR 0.12
        ]
        # id=0 / id=1 = 3.0 ≥ 1.2, id=0 / id=2 = 2.5 ≥ 1.2 → id=0 wins
        assert determine_winner(variants) == 0

    def test_three_variants_no_winner(self):
        variants = [
            {"id": 0, "views": 1000, "clicks": 200},  # CTR 0.20
            {"id": 1, "views": 1000, "clicks": 180},  # CTR 0.18
            {"id": 2, "views": 1000, "clicks": 195},  # CTR 0.195
        ]
        assert determine_winner(variants) is None

    def test_integer_ids_and_string_values(self):
        # Matches the actual wire format from SNS
        variants = [
            {"id": 0, "views": "5464", "clicks": "120"},
            {"id": 1, "views": "5470", "clicks": "160"},
            {"id": 2, "views": "5468", "clicks": "170"},
        ]
        assert determine_winner(variants) is None