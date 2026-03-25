"""
AB Test Analyzer Lambda
Receives SNS messages with AB test interim results, determines the winner,
and writes the result to a PostgreSQL RDS database.
"""

import json
import logging

import psycopg2

from db import get_db_connection, init_db_schema
from analyzer import compute_ctr, determine_winner, parse_sns_message

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger()

# Run schema initialisation once per cold start
_schema_initialised = False


def _ensure_schema(conn) -> None:
    global _schema_initialised
    if not _schema_initialised:
        init_db_schema(conn)
        _schema_initialised = True


def lambda_handler(event: dict, context) -> dict:
    """
    Main Lambda entry point.

    Expected SNS message payload:
    {
        "test_id": "string",
        "content_id": "string",
        "variants": [
            {
                "id": int,
                "clicks": "string",
                "views": "string"
            },
            ...
        ],
        "msg_timestamp": "string"
    }
    """
    logger.info("Lambda invoked [request_id=%s]", context.aws_request_id)

    results = []
    records = event.get("Records", [])

    if records:
        with get_db_connection() as conn:
            _ensure_schema(conn)
            for record in records:
                try:
                    result = process_record(record, context.aws_request_id, conn)
                    results.append({"status": "success", "test_id": result.get("test_id")})
                except ValueError as exc:
                    logger.error("Validation error [request_id=%s]: %s", context.aws_request_id, exc)
                    results.append({"status": "error", "error": str(exc)})
                except psycopg2.Error as exc:
                    logger.error("Database error [request_id=%s]: %s", context.aws_request_id, exc)
                    results.append({"status": "error", "error": "Database error"})
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error("Unexpected error [request_id=%s]: %s", context.aws_request_id, exc, exc_info=True)
                    results.append({"status": "error", "error": "Internal error"})

    logger.info("Lambda finished [request_id=%s, processed=%d]", context.aws_request_id, len(results))
    errors = sum(1 for r in results if r["status"] == "error")
    if errors == 0:
        status_code = 200
    elif errors < len(results):
        status_code = 207
    else:
        status_code = 500
    return {"statusCode": status_code, "body": json.dumps(results)}


def process_record(record: dict, request_id: str, conn) -> dict:
    """Parse one SNS record, run analysis and persist the result."""

    sns_payload = parse_sns_message(record)
    test_id: str = sns_payload["test_id"]

    logger.info("Processing AB test [request_id=%s, test_id=%s]", request_id, test_id)

    winner = determine_winner(sns_payload["variants"])

    logger.info("Winner determined [test_id=%s, winner=%s]", test_id, winner if winner is not None else "no_winner")

    save_result(conn, sns_payload, winner)

    return {"test_id": test_id, "winner": winner}


def save_result(conn, payload: dict, winner: int | None) -> None:
    """Persist the analysis result and variant snapshots to the database."""

    test_id = payload["test_id"]

    with conn.cursor() as cur:
        # Upsert the test result
        cur.execute(
            """
            INSERT INTO ab_test_results (
                test_id, test_name, evaluated_at, winner_variant, raw_payload
            ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (test_id) DO UPDATE SET
                test_name       = EXCLUDED.test_name,
                evaluated_at    = EXCLUDED.evaluated_at,
                winner_variant  = EXCLUDED.winner_variant,
                raw_payload     = EXCLUDED.raw_payload,
                updated_at      = NOW();
            """,
            (
                test_id,
                payload.get("content_id", ""),
                payload.get("msg_timestamp"),
                winner,
                json.dumps(payload),
            ),
        )

        # Upsert each variant snapshot
        for variant in payload.get("variants", []):
            impressions = int(variant.get("views", 0))
            clicks = int(variant.get("clicks", 0))
            ctr = compute_ctr(impressions, clicks)

            cur.execute(
                """
                INSERT INTO ab_test_variant_snapshots (
                    test_id, variant_id, impressions, clicks, ctr
                ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (test_id, variant_id) DO UPDATE SET
                    impressions = EXCLUDED.impressions,
                    clicks      = EXCLUDED.clicks,
                    ctr         = EXCLUDED.ctr;
                """,
                (test_id, variant["id"], impressions, clicks, round(ctr, 6)),
            )

        conn.commit()

    logger.info("Result saved to database [test_id=%s]", test_id)