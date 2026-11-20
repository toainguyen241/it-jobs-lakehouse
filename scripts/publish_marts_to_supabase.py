import os
from collections.abc import Mapping, Sequence

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import URL, Connection, Engine
from sqlalchemy.types import NullType, Text, TypeEngine


def require_env(name: str, environ: Mapping[str, str] | None = None) -> str:
    environ = os.environ if environ is None else environ
    value = environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _array_column_dtypes(frame: pd.DataFrame) -> dict[str, ARRAY]:

    overrides: dict[str, ARRAY] = {}
    for column in frame.columns:
        non_null = frame[column].dropna()
        if len(non_null) > 0 and non_null.map(lambda v: isinstance(v, list)).all():
            overrides[column] = ARRAY(Text())
    return overrides


def load_local_dtypes(
    local_engine: Engine,
    mart: str,
    frame: pd.DataFrame,
    schema: str = "gold",
) -> dict[str, TypeEngine]:

    reflected = inspect(local_engine).get_columns(mart, schema=schema)
    return build_dtype_overrides(reflected, frame)


def build_dtype_overrides(
    reflected_columns: Sequence[Mapping[str, object]],
    frame: pd.DataFrame,
) -> dict[str, TypeEngine]:
    overrides: dict[str, TypeEngine] = {}
    for column in reflected_columns:
        name = column["name"]
        col_type = column["type"]
        if name not in frame.columns or isinstance(col_type, NullType):
            continue
        overrides[str(name)] = col_type  # type: ignore
    return overrides


MARTS = (
    "mart_overview_kpis",
    "mart_company_hiring",
    "mart_cross_source_duplicates",
    "mart_data_engineer_jobs",
    "mart_data_quality",
    "mart_domestic_vs_international_jobs",
    "mart_hot_skills",
    "mart_jobs_by_country",
    "mart_jobs_by_skill",
    "mart_jobs_by_work_type",
    "mart_job_market_overview",
    "mart_salary_benchmark",
    "mart_salary_by_source",
    "mart_skills_demand",
    "mart_skill_trends_by_year",
)


def build_local_database_url(
    environ: Mapping[str, str] | None = None,
) -> URL:
    environ = os.environ if environ is None else environ
    return URL.create(
        drivername="postgresql+psycopg2",
        username=require_env("POSTGRES_USER", environ),
        password=require_env("POSTGRES_PASSWORD", environ),
        host=environ.get("POSTGRES_HOST", "localhost"),
        port=int(environ.get("POSTGRES_PORT", "5433")),
        database=require_env("POSTGRES_DB", environ),
    )


def load_local_marts(
    local_engine: Engine,
    marts: Sequence[str] = MARTS,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for mart in marts:
        frames[mart] = pd.read_sql_query(
            text(f'SELECT * FROM gold."{mart}"'),
            local_engine,
        )
    return frames


_TYPE_FAMILIES: dict[str, str] = {
    "smallint": "numeric",
    "integer": "numeric",
    "bigint": "numeric",
    "numeric": "numeric",
    "real": "numeric",
    "double precision": "numeric",
    "text": "text",
    "character varying": "text",
    "character": "text",
    "boolean": "boolean",
    "date": "date",
    "timestamp without time zone": "timestamp",
    "timestamp with time zone": "timestamp",
}


def _type_family(data_type: str) -> str:
    """Map PostgreSQL data_type sang một nhóm kiểu dữ liệu để so sánh."""
    return _TYPE_FAMILIES.get(data_type, data_type)


def _read_column_types(
    conn: Connection,
    marts: Sequence[str],
    schema: str = "gold",
) -> dict[str, dict[str, str]]:
    types: dict[str, dict[str, str]] = {}
    for mart in marts:
        rows = conn.execute(
            text(
                "SELECT column_name, data_type "
                "FROM information_schema.columns "
                "WHERE table_schema = :schema AND table_name = :mart"
            ),
            {"schema": schema, "mart": mart},
        ).all()
        types[mart] = {row.column_name: row.data_type for row in rows}
    return types


def load_column_types(
    engine: Engine,
    marts: Sequence[str],
    schema: str = "gold",
) -> dict[str, dict[str, str]]:

    with engine.connect() as conn:
        return _read_column_types(conn, marts, schema)


def _verify_counts(
    conn: Connection,
    expected_counts: Mapping[str, int],
) -> dict[str, int]:
    actual_counts: dict[str, int] = {}
    for mart, expected in expected_counts.items():
        actual = conn.execute(text(f'SELECT count(*) FROM gold."{mart}"')).scalar_one()
        actual_counts[mart] = int(actual)
        if actual != expected:
            raise RuntimeError(
                f"Row-count mismatch for gold.{mart}: expected {expected}, got {actual}"
            )
    return actual_counts


def _verify_column_types(
    local_types: Mapping[str, Mapping[str, str]],
    cloud_types: Mapping[str, Mapping[str, str]],
    marts: Sequence[str],
) -> None:
    for mart in marts:
        local_cols = local_types.get(mart, {})
        cloud_cols = cloud_types.get(mart, {})
        if local_cols.keys() != cloud_cols.keys():
            missing = set(local_cols) - set(cloud_cols)
            extra = set(cloud_cols) - set(local_cols)
            raise RuntimeError(
                f"Column mismatch for gold.{mart}: "
                f"missing on Supabase={sorted(missing)}, "
                f"unexpected on Supabase={sorted(extra)}"
            )
        drifted = {
            column: (local_cols[column], cloud_cols[column])
            for column in local_cols
            if _type_family(local_cols[column]) != _type_family(cloud_cols[column])
        }
        if drifted:
            raise RuntimeError(
                f"Column-type drift for gold.{mart} (local vs Supabase): {drifted}"
            )


def publish_marts(
    cloud_engine: Engine,
    frames: Mapping[str, pd.DataFrame],
    local_engine: Engine | None = None,
) -> dict[str, int]:
    expected_counts = {mart: len(frame) for mart, frame in frames.items()}
    marts = list(frames)
    local_types = load_column_types(local_engine, marts) if local_engine else None

    with cloud_engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold"))
        for mart, frame in frames.items():
            print(f"Publishing gold.{mart} ...")
            if local_engine is not None:
                dtype = load_local_dtypes(local_engine, mart, frame)
            else:
                dtype = _array_column_dtypes(frame)
            frame.to_sql(
                mart,
                conn,
                schema="gold",
                if_exists="replace",
                index=False,
                method="multi",
                chunksize=1000,
                dtype=dtype or None,  # type: ignore
            )
            print(f"  -> {len(frame):,} rows")

        actual_counts = _verify_counts(conn, expected_counts)
        if local_types is not None:
            _verify_column_types(local_types, _read_column_types(conn, marts), marts)

    return actual_counts


def main() -> None:
    load_dotenv()
    local_engine = create_engine(build_local_database_url(), pool_pre_ping=True)
    cloud_engine = create_engine(
        require_env("SUPABASE_DB_URL"),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 20},
    )

    try:
        frames = load_local_marts(local_engine)
        counts = publish_marts(cloud_engine, frames, local_engine=local_engine)
    finally:
        local_engine.dispose()
        cloud_engine.dispose()

    print(f"Publish complete: {len(counts)} marts verified.")


if __name__ == "__main__":
    main()
