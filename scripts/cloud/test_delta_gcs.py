from __future__ import annotations

import os

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake


def main() -> None:
    bucket_name = os.environ["GCS_BUCKET"]
    table_uri = f"gs://{bucket_name}/delta/test_jobs"

    data = pa.table(
        {
            "job_id": ["test-001", "test-002"],
            "source_name": ["itviec", "topcv"],
        }
    )

    write_deltalake(
        table_uri,
        data,
        mode="overwrite",
        schema_mode="overwrite",
    )

    delta_table = DeltaTable(table_uri)

    print(f"Delta URI: {table_uri}")
    print(f"Version: {delta_table.version()}")
    print(f"Rows: {delta_table.to_pyarrow_table().num_rows}")


if __name__ == "__main__":
    main()
