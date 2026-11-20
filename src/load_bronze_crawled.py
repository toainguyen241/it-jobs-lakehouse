from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from deltalake import DeltaTable, write_deltalake
from psycopg2.extras import Json, execute_values

from src.config import get_minio_config, get_postgres_config
from src.incremental_state import record_crawl_outcomes
from src.it_job_filter import RejectedJob, filter_non_it_rows

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = [
    "job_id_nk",
    "source_name",
    "scraped_at",
    "job_title",
    "company_name",
    "experience",
    "salary_text",
    "location",
    "skills",
    "job_type",
    "job_description",
    "company_size",
    "industry",
    "country",
    "posted_date",
    "time_info_raw",
    "time_info_label",
]

PG_TOP_LEVEL_COLUMNS = ["job_id_nk", "source_name", "scraped_at"]
TARGET_PG_TABLE = "bronze.raw_jobs_crawled"


def to_json_compatible(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_compatible(item) for item in value]

    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return to_json_compatible(tolist())

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    item = getattr(value, "item", None)
    if callable(item):
        return to_json_compatible(item())

    return value


def validate_schema(df: pd.DataFrame, expected_source_name: str) -> None:
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Parquet thieu {len(missing)} cot: {sorted(missing)}.")
    if df.empty:
        raise ValueError("Parquet rong -- khong co gi de load.")

    actual_sources = set(df["source_name"].unique())
    if actual_sources != {expected_source_name}:
        raise ValueError(
            f"--source-name={expected_source_name!r} nhung file thuc chua "
            f"source_name={actual_sources}."
        )

    if df["job_id_nk"].isnull().any():
        raise ValueError("Co dong NULL job_id_nk -- khong the dedup an toan.")
    if (df["job_id_nk"].astype(str).str.strip() == "").any():
        raise ValueError("Co dong job_id_nk rong -- khong the dedup an toan.")

    duplicated = df.duplicated(subset=["source_name", "job_id_nk"], keep=False)
    if duplicated.any():
        sample = sorted(df.loc[duplicated, "job_id_nk"].astype(str).unique())[:5]
        raise ValueError(
            f"Batch co {int(duplicated.sum())} dong trung "
            f"(source_name, job_id_nk), vi du: {sample}. "
            "Crawler phai dedup truoc khi ghi Parquet."
        )

    logger.info("Schema hop le: %d dong, source_name=%s", len(df), expected_source_name)


def read_parquet(parquet_path: Path, expected_source_name: str) -> pd.DataFrame:
    if not parquet_path.exists():
        raise FileNotFoundError(f"Khong tim thay file: {parquet_path}.")

    df = pd.read_parquet(parquet_path)
    logger.info("Doc %d dong tu %s", len(df), parquet_path)
    validate_schema(df, expected_source_name)
    return df[EXPECTED_COLUMNS].copy()


ALL_REJECTED_RAISE_MIN_ROWS = 10


def validate_it_scope(df: pd.DataFrame) -> tuple[pd.DataFrame, list[RejectedJob]]:
    accepted, rejected = filter_non_it_rows(df)
    logger.info(
        "IT scope check: accepted=%d, rejected_non_it=%d",
        len(accepted),
        len(rejected),
    )
    for item in rejected[:20]:
        logger.warning(
            "Rejected non-IT job: job_id_nk=%s, title=%r, reason=%s",
            item.job_id_nk,
            item.job_title,
            item.reason,
        )
    if len(rejected) > 20:
        logger.warning("... and %d additional rejected rows", len(rejected) - 20)
    if accepted.empty:
        if len(df) >= ALL_REJECTED_RAISE_MIN_ROWS:
            raise ValueError(
                f"IT scope check rejected every row ({len(df)} rows >= "
                f"{ALL_REJECTED_RAISE_MIN_ROWS}); nghi loi bo loc hoac du lieu "
                "nguon, khong ghi state/Bronze."
            )
        logger.warning("IT scope check rejected every row; nothing will be loaded.")
    return accepted, rejected


def write_to_delta(df: pd.DataFrame, source_name: str) -> None:
    minio_config = get_minio_config()
    table_uri = minio_config.table_uri(f"bronze/{source_name}")
    storage_options = minio_config.storage_options

    table_exists = DeltaTable.is_deltatable(table_uri, storage_options=storage_options)

    if not table_exists:
        logger.info("Delta table chua ton tai tai %s -- tao moi.", table_uri)
        write_deltalake(table_uri, df, mode="append", storage_options=storage_options)
        logger.info("Da tao Delta table voi %d dong.", len(df))
        return

    logger.info("Delta table da ton tai -- chay MERGE INTO dedup.")
    dt = DeltaTable(table_uri, storage_options=storage_options)

    (
        dt.merge(
            source=df,
            predicate=(
                "target.job_id_nk = source.job_id_nk "
                "AND target.source_name = source.source_name"
            ),
            source_alias="source",
            target_alias="target",
        )
        .when_matched_update_all()
        .when_not_matched_insert_all()
        .execute()
    )
    logger.info("MERGE INTO hoan tat cho %s.", table_uri)


def upsert_to_postgres(df: pd.DataFrame, dsn: str, batch_size: int = 500) -> int:
    payload_columns = [c for c in EXPECTED_COLUMNS if c not in PG_TOP_LEVEL_COLUMNS]

    rows = []
    for record in df.to_dict(orient="records"):
        payload = {k: to_json_compatible(record[k]) for k in payload_columns}
        rows.append(
            (
                record["job_id_nk"],
                record["source_name"],
                record["scraped_at"],
                Json(payload),
            )
        )

    upsert_sql = f"""
        INSERT INTO {TARGET_PG_TABLE} (job_id_nk, source_name, scraped_at, payload)
        VALUES %s
        ON CONFLICT (job_id_nk, source_name)
        DO UPDATE SET
            scraped_at = EXCLUDED.scraped_at,
            payload    = EXCLUDED.payload,
            loaded_at  = now()
    """

    conn = psycopg2.connect(dsn)
    try:
        with conn:  # noqa: SIM117
            with conn.cursor() as cur:
                execute_values(cur, upsert_sql, rows, page_size=batch_size)
        logger.info("Upsert %d dong vao %s", len(rows), TARGET_PG_TABLE)
    finally:
        conn.close()

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet-path", type=Path, required=True)
    parser.add_argument(
        "--source-name",
        type=str,
        required=True,
        choices=[
            "itviec",
            "topdev",
            "topcv",
            "indeed",
            "weworkremotely",
            "remoteok",
        ],
        help="Phai khop voi source_name that trong file Parquet.",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate schema and IT scope without writing Delta/PostgreSQL.",
    )
    args = parser.parse_args()

    try:
        df = read_parquet(args.parquet_path, args.source_name)
        df, rejected = validate_it_scope(df)
        if args.check_only:
            logger.info("CHECK PASSED: no data was written.")
            return

        if df.empty:
            record_crawl_outcomes(
                args.source_name,
                [
                    (item.job_id_nk, None, f"preload_non_it:{item.reason}")
                    for item in rejected
                ],
                status="rejected",
            )
            logger.info("Moi dong deu non-IT: da ghi nhan rejected, khong load Bronze.")
            return

        pg_config = get_postgres_config()
        write_to_delta(df, args.source_name)
        row_count = upsert_to_postgres(df, pg_config.dsn)
        if rejected:
            record_crawl_outcomes(
                args.source_name,
                [
                    (item.job_id_nk, None, f"preload_non_it:{item.reason}")
                    for item in rejected
                ],
                status="rejected",
            )
        record_crawl_outcomes(
            args.source_name,
            [(str(job_id), None, None) for job_id in df["job_id_nk"].dropna().unique()],
            status="loaded",
        )
        logger.info(
            "HOAN TAT: %d dong da load vao Delta (MinIO) + %s",
            row_count,
            TARGET_PG_TABLE,
        )
    except Exception:
        logger.exception("Load Bronze crawled THAT BAI.")
        sys.exit(1)


if __name__ == "__main__":
    main()
