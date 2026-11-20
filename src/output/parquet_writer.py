from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from src.schemas.raw_job import RawJobPosting

JOB_SCHEMA = pa.schema(
    [
        pa.field("job_id_nk", pa.string(), nullable=False),
        pa.field("source_name", pa.string(), nullable=False),
        pa.field("scraped_at", pa.timestamp("us", tz="UTC"), nullable=False),
        pa.field("job_title", pa.string(), nullable=False),
        pa.field("company_name", pa.string(), nullable=False),
        pa.field("experience", pa.string()),
        pa.field("salary_text", pa.string()),
        pa.field("location", pa.string()),
        pa.field("skills", pa.list_(pa.string()), nullable=False),
        pa.field("job_type", pa.string()),
        pa.field("job_description", pa.string()),
        pa.field("company_size", pa.string()),
        pa.field("industry", pa.string()),
        pa.field("country", pa.string()),
        pa.field("posted_date", pa.date32()),
        pa.field("time_info_raw", pa.string()),
        pa.field("time_info_label", pa.string()),
    ]
)


def write_jobs_parquet(
    jobs: list[RawJobPosting],
    source_name: str,
    output_root: str | Path = "data/raw",
) -> Path:
    if not re.fullmatch(r"[a-z0-9_-]+", source_name):
        raise ValueError(f"source_name khong hop le: {source_name!r}")

    output_dir = Path(output_root) / source_name
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005
    output_path = output_dir / f"jobs_{timestamp}.parquet"

    rows = [job.model_dump() for job in jobs]
    table = pa.Table.from_pylist(rows, schema=JOB_SCHEMA)
    pq.write_table(table, output_path, compression="snappy")
    return output_path
