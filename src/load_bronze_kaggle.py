from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from src.config import get_postgres_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "job_id",
    "job_title",
    "salary_usd",
    "salary_currency",
    "experience_level",
    "employment_type",
    "company_location",
    "company_size",
    "employee_residence",
    "remote_ratio",
    "required_skills",
    "education_required",
    "years_experience",
    "industry",
    "posting_date",
    "application_deadline",
    "job_description_length",
    "benefits_score",
    "company_name",
]

TARGET_TABLE = "bronze.raw_jobs_kaggle_global_ai_2025"

# Thứ tự cột phải khớp với thứ tự INSERT bên dưới.
INSERT_COLUMNS = REQUIRED_COLUMNS


def validate_schema(df: pd.DataFrame) -> None:
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(
            f"CSV thieu {len(missing)} cot bat buoc: {sorted(missing)}. "
            f"Kiem tra lai file co dung la Kaggle 'Global AI Job Market & "
            f"Salary Trends 2025' khong, hay da doi schema."
        )
    if df.empty:
        raise ValueError("CSV rong -- khong co gi de load.")
    logger.info("Schema hop le: %d cot bat buoc deu co mat.", len(REQUIRED_COLUMNS))


def load_csv(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Khong tim thay file: {csv_path}")

    df = pd.read_csv(csv_path)
    logger.info("Doc %d dong tu %s", len(df), csv_path)
    validate_schema(df)

    # Chỉ giữ đúng các cột cần, đúng thứ tự — tránh lỗi nếu CSV có thêm cột thừa ngoài dự kiến.
    df = df[REQUIRED_COLUMNS].copy()

    # NaN của pandas phải convert về None để psycopg2 ghi NULL đúng.
    df = df.astype(object).where(pd.notnull(df), None)

    return df


def truncate_and_load(df: pd.DataFrame, dsn: str, batch_size: int = 1000) -> int:
    rows = [tuple(row) for row in df[INSERT_COLUMNS].itertuples(index=False, name=None)]

    insert_sql = f"""
        INSERT INTO {TARGET_TABLE} ({", ".join(INSERT_COLUMNS)})
        VALUES %s
    """

    conn = psycopg2.connect(dsn)
    try:
        with conn:  # noqa: SIM117
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {TARGET_TABLE}")
                logger.info("Da TRUNCATE %s", TARGET_TABLE)

                execute_values(cur, insert_sql, rows, page_size=batch_size)
                logger.info("Da insert %d dong vao %s", len(rows), TARGET_TABLE)
    finally:
        conn.close()

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv-path",
        type=Path,
        required=True,
        help="Duong dan toi file CSV Kaggle da tai ve.",
    )
    args = parser.parse_args()

    pg_config = get_postgres_config()

    try:
        df = load_csv(args.csv_path)
        row_count = truncate_and_load(df, pg_config.dsn)
        logger.info("HOAN TAT: %d dong da load vao %s", row_count, TARGET_TABLE)
    except Exception:
        logger.exception("Load Kaggle Bronze THAT BAI.")
        sys.exit(1)


if __name__ == "__main__":
    main()
