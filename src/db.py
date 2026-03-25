"""
Database helpers: connection management and schema initialization.

Credentials are read from AWS Secrets Manager at runtime; the secret must
contain a JSON object with the keys:
    host, port, dbname, username, password
"""

import json
import logging
import os
from contextlib import contextmanager

import boto3
import psycopg2
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Environment variable that holds the Secrets Manager secret ARN
SECRET_ARN_ENV = "DB_SECRET_ARN"

# DDL executed once per cold-start (idempotent)
SCHEMA_DDL = """
             CREATE TABLE IF NOT EXISTS ab_test_results (
                                                            test_id         TEXT        PRIMARY KEY,
                                                            test_name       TEXT        NOT NULL DEFAULT '',
                                                            evaluated_at    TIMESTAMPTZ,
                                                            winner_variant  BIGINT,
                                                            raw_payload     JSONB,
                                                            created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                 updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
                 );

             CREATE TABLE IF NOT EXISTS ab_test_variant_snapshots (
                                                                      id              BIGSERIAL   PRIMARY KEY,
                                                                      test_id         TEXT        NOT NULL REFERENCES ab_test_results(test_id) ON DELETE CASCADE,
                 variant_id      BIGINT      NOT NULL,
                 impressions     BIGINT      NOT NULL DEFAULT 0,
                 clicks          BIGINT      NOT NULL DEFAULT 0,
                 ctr             NUMERIC(10, 6) NOT NULL DEFAULT 0,
                 recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                 UNIQUE (test_id, variant_id)
                 );

             CREATE INDEX IF NOT EXISTS idx_results_evaluated_at
                 ON ab_test_results (evaluated_at DESC);

             CREATE INDEX IF NOT EXISTS idx_snapshots_test_id
                 ON ab_test_variant_snapshots (test_id); \
             """

# Module-level cache to avoid repeated Secrets Manager calls within the same
# execution environment (warm Lambda invocations)
_cached_credentials: dict | None = None


def _get_db_credentials() -> dict:
    """Fetch database credentials from AWS Secrets Manager (with cache)."""
    global _cached_credentials
    if _cached_credentials is not None:
        return _cached_credentials

    secret_arn = os.environ.get(SECRET_ARN_ENV)
    if not secret_arn:
        raise EnvironmentError(
            f"Environment variable '{SECRET_ARN_ENV}' is not set"
        )

    client = boto3.client("secretsmanager")
    try:
        response = client.get_secret_value(SecretId=secret_arn)
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        raise RuntimeError(
            f"Failed to retrieve secret '{secret_arn}': {error_code}"
        ) from exc

    secret_string = response.get("SecretString")
    if not secret_string:
        raise RuntimeError("Secret has no SecretString value")

    credentials = json.loads(secret_string)
    _cached_credentials = credentials
    logger.info("Database credentials loaded from Secrets Manager")
    return credentials


@contextmanager
def get_db_connection():
    """
    Context manager that yields a psycopg2 connection.
    The connection is closed automatically; callers must commit explicitly.
    """
    creds = _get_db_credentials()
    conn = psycopg2.connect(
        host=creds["host"],
        port=int(creds.get("port", 5432)),
        dbname=creds["dbname"],
        user=creds["username"],
        password=creds["password"],
        connect_timeout=10,
        sslmode=os.environ.get("DB_SSLMODE", "require"),
    )
    try:
        yield conn
    finally:
        conn.close()


def init_db_schema(conn) -> None:
    """Create tables and indexes if they do not yet exist (idempotent)."""
    with conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)
    conn.commit()
    logger.info("Database schema initialised (or already up to date)")