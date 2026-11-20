from __future__ import annotations

import argparse
import logging
import os

from deltalake import DeltaTable, write_deltalake

from src.config import get_minio_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy one Delta table from MinIO to GCS and verify it."
    )
    parser.add_argument(
        "--source-name",
        required=True,
        choices=["itviec", "topcv", "topdev"],
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the destination Delta table if it already exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    gcs_bucket = os.environ["GCS_BUCKET"]
    minio_config = get_minio_config()

    source_uri = minio_config.table_uri(f"bronze/{args.source_name}")
    destination_uri = f"gs://{gcs_bucket}/bronze/{args.source_name}"

    logger.info("Reading source Delta table: %s", source_uri)
    source_table = DeltaTable(
        source_uri,
        storage_options=minio_config.storage_options,
    )
    source_data = source_table.to_pyarrow_table()

    source_rows = source_data.num_rows
    source_schema = source_data.schema

    logger.info(
        "Source version=%d rows=%d",
        source_table.version(),
        source_rows,
    )

    mode = "overwrite" if args.overwrite else "error"
    logger.info("Writing destination Delta table: %s", destination_uri)

    write_deltalake(
        destination_uri,
        source_data,
        mode=mode,
    )

    destination_table = DeltaTable(destination_uri)
    destination_data = destination_table.to_pyarrow_table()

    destination_rows = destination_data.num_rows
    destination_schema = destination_data.schema

    if destination_rows != source_rows:
        raise RuntimeError(
            f"Row-count mismatch: MinIO={source_rows}, GCS={destination_rows}"
        )

    if destination_schema != source_schema:
        raise RuntimeError("Schema mismatch between MinIO source and GCS destination.")

    logger.info(
        "Migration verified: source=%s destination=%s rows=%d destination_version=%d",
        source_uri,
        destination_uri,
        destination_rows,
        destination_table.version(),
    )


if __name__ == "__main__":
    main()
