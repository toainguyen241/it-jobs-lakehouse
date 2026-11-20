from __future__ import annotations

import psycopg2
from psycopg2.extras import execute_values

from src.config import get_postgres_config

TARGET_TABLE = "bronze.raw_jobs_crawled"
STATE_TABLE = "bronze.crawl_job_state"

STATE_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {STATE_TABLE} (
    source_name     TEXT        NOT NULL,
    job_id_nk       TEXT        NOT NULL,
    job_url         TEXT,
    status          TEXT        NOT NULL,
    reason          TEXT,
    attempts        INTEGER     NOT NULL DEFAULT 0,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_name, job_id_nk),
    CONSTRAINT ck_crawl_job_state_status
        CHECK (status IN ('loaded', 'rejected', 'failed', 'quarantined'))
);
CREATE INDEX IF NOT EXISTS idx_crawl_job_state_status
    ON {STATE_TABLE} (source_name, status);
"""

STATE_TABLE_MIGRATION_SQL = f"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'bronze' AND table_name = 'crawl_job_state'
          AND column_name = 'attempts'
    ) THEN
        ALTER TABLE {STATE_TABLE}
            ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_crawl_job_state_status'
          AND conrelid = '{STATE_TABLE}'::regclass
          AND pg_get_constraintdef(oid) LIKE '%quarantined%'
    ) THEN
        ALTER TABLE {STATE_TABLE}
            DROP CONSTRAINT IF EXISTS ck_crawl_job_state_status;
        ALTER TABLE {STATE_TABLE}
            ADD CONSTRAINT ck_crawl_job_state_status
            CHECK (status IN ('loaded', 'rejected', 'failed', 'quarantined'));
    END IF;
END $$;
"""

MAX_ATTEMPTS = 3

STATE_TABLE_BACKFILL_SQL = f"""
INSERT INTO {STATE_TABLE} (source_name, job_id_nk, status)
SELECT source_name, job_id_nk, 'loaded'
FROM {TARGET_TABLE}
ON CONFLICT (source_name, job_id_nk) DO NOTHING
"""

SUPPORTED_SOURCES = {
    "itviec",
    "topdev",
    "topcv",
    "indeed",
    "weworkremotely",
    "remoteok",
}


def _validate_source(source_name: str) -> None:
    if source_name not in SUPPORTED_SOURCES:
        raise ValueError(f"source_name khong duoc ho tro: {source_name!r}")


def _ensure_state_table(cur) -> None:

    cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (STATE_TABLE,))
    cur.execute(STATE_TABLE_DDL)
    cur.execute(STATE_TABLE_MIGRATION_SQL)
    cur.execute(STATE_TABLE_BACKFILL_SQL)


def load_existing_job_ids(source_name: str) -> set[str]:
    """Load job_id_nk đã có trong Bronze (loaded/rejected/quarantined). Dùng để incremental crawl: không crawl lại job đã load/rejected/quarantined."""
    _validate_source(source_name)

    conn = psycopg2.connect(get_postgres_config().dsn)
    try:
        with conn, conn.cursor() as cur:
            _ensure_state_table(cur)
            cur.execute(
                f"""
                SELECT job_id_nk FROM {TARGET_TABLE} WHERE source_name = %s
                UNION
                SELECT job_id_nk FROM {STATE_TABLE}
                WHERE source_name = %s
                  AND status IN ('loaded', 'rejected', 'quarantined')
                """,
                (source_name, source_name),
            )
            return {row[0] for row in cur.fetchall() if row[0]}
    finally:
        conn.close()


def record_crawl_outcomes(
    source_name: str,
    outcomes: list[tuple[str, str | None, str | None]],
    status: str,
) -> int:
    """Upsert crawl state. Technical failures must never call this function."""
    _validate_source(source_name)
    if status not in {"loaded", "rejected"}:
        raise ValueError(f"crawl status khong hop le: {status!r}")
    if not outcomes:
        return 0

    # Cùng 1 job_id không được xuất hiện 2 lần trong 1 INSERT ... ON CONFLICT.
    deduped = {job_id: (url, reason) for job_id, url, reason in outcomes}
    rows = [
        (source_name, job_id, url, status, reason)
        for job_id, (url, reason) in deduped.items()
    ]
    conn = psycopg2.connect(get_postgres_config().dsn)
    try:
        with conn, conn.cursor() as cur:
            _ensure_state_table(cur)
            execute_values(
                cur,
                f"""
                INSERT INTO {STATE_TABLE}
                    (source_name, job_id_nk, job_url, status, reason)
                VALUES %s
                ON CONFLICT (source_name, job_id_nk)
                DO UPDATE SET
                    job_url = coalesce(EXCLUDED.job_url, {STATE_TABLE}.job_url),
                    status = EXCLUDED.status,
                    reason = EXCLUDED.reason,
                    last_seen_at = now()
                """,
                rows,
                page_size=500,
            )
        return len(rows)
    finally:
        conn.close()


def record_crawl_failures(
    source_name: str,
    failures: list[tuple[str, str | None, str | None]],
    max_attempts: int = MAX_ATTEMPTS,
) -> list[tuple[str, str, int]]:
    """Upsert crawl state cho job bị lỗi (failed/quarantined). Nếu job đã bị lỗi trước đó, tăng attempts lên 1. Nếu attempts >= max_attempts thì quarantine.
    Return: list[tuple[job_id_nk, status, attempts]] của các job đã ghi nhớ.
    """
    _validate_source(source_name)
    max_attempts = int(max_attempts)
    if max_attempts < 1:
        raise ValueError("max_attempts phai >= 1.")
    if not failures:
        return []

    deduped = {job_id: (url, reason) for job_id, url, reason in failures}
    first_status = "quarantined" if max_attempts <= 1 else "failed"
    rows = [
        (source_name, job_id, url, first_status, reason)
        for job_id, (url, reason) in deduped.items()
    ]
    conn = psycopg2.connect(get_postgres_config().dsn)
    try:
        with conn, conn.cursor() as cur:
            _ensure_state_table(cur)
            result = execute_values(
                cur,
                f"""
                INSERT INTO {STATE_TABLE}
                    (source_name, job_id_nk, job_url, status, reason, attempts)
                VALUES %s
                ON CONFLICT (source_name, job_id_nk)
                DO UPDATE SET
                    job_url = coalesce(EXCLUDED.job_url, {STATE_TABLE}.job_url),
                    reason = EXCLUDED.reason,
                    attempts = {STATE_TABLE}.attempts + 1,
                    status = CASE
                        WHEN {STATE_TABLE}.attempts + 1 >= {max_attempts}
                            THEN 'quarantined' ELSE 'failed' END,
                    last_seen_at = now()
                WHERE {STATE_TABLE}.status IN ('failed', 'quarantined')
                RETURNING job_id_nk, status, attempts
                """,
                rows,
                template="(%s, %s, %s, %s, %s, 1)",
                page_size=500,
                fetch=True,
            )
            return [(r[0], r[1], r[2]) for r in result]
    finally:
        conn.close()
