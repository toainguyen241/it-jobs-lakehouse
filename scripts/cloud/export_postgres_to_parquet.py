from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import psycopg2

from src.config import get_postgres_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

OUTPUT_ROOT = Path("tmp/bigquery_export")

EXPORT_OBJECTS = {
    "silver": [
        "silver_jobs_unified",
        "fx_rates",
    ],
    "gold": [
        "dim_companies",
        "dim_date",
        "dim_locations",
        "dim_skills",
        "fact_job_postings",
        "bridge_job_skills",
    ],
}


def export_object(
    conn,
    schema_name: str,
    object_name: str,
) -> int:
    output_dir = OUTPUT_ROOT / schema_name
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{object_name}.parquet"

    query = f'SELECT * FROM "{schema_name}"."{object_name}"'

    logger.info(
        "Exporting %s.%s",
        schema_name,
        object_name,
    )

    df = pd.read_sql_query(query, conn)

    if df.empty:
        logger.warning(
            "%s.%s tra ve 0 rows",
            schema_name,
            object_name,
        )

    df.to_parquet(
        output_path,
        engine="pyarrow",
        index=False,
        compression="snappy",
    )

    logger.info(
        "Exported %d rows -> %s",
        len(df),
        output_path,
    )

    return len(df)


def main() -> None:
    pg_config = get_postgres_config()

    total_rows = 0

    conn = psycopg2.connect(pg_config.dsn)

    try:
        for schema_name, objects in EXPORT_OBJECTS.items():
            for object_name in objects:
                row_count = export_object(
                    conn,
                    schema_name,
                    object_name,
                )
                total_rows += row_count
    finally:
        conn.close()

    logger.info(
        "EXPORT COMPLETE: %d total rows",
        total_rows,
    )


if __name__ == "__main__":
    main()
