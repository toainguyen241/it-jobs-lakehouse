# GCS optional

These scripts are optional utilities and are not part of the Airflow DAG. The local pipeline continues to use S3-compatible object storage (the MinIO-compatible `pgsty/silo` image in Docker Compose):

```text
Airflow -> Delta Lake on S3-compatible storage -> PostgreSQL -> dbt -> Streamlit
```

## Prerequisites

Run every command from the repository root.

```powershell
gcloud auth application-default login
$env:GOOGLE_APPLICATION_CREDENTIALS="$env:APPDATA\gcloud\application_default_credentials.json"
```

Set `GCS_BUCKET` in the `.env` file in the project root:

```env
GCS_BUCKET=your-gcs-bucket
```

The two test scripts read `GCS_BUCKET` straight from the environment and do not load
`.env` themselves, so run every command below through `uv run --env-file .env`.

## Test GCS connectivity

```powershell
uv run --env-file .env python scripts/cloud/test_gcs_connection.py
```

## Test Delta Lake on GCS

```powershell
uv run --env-file .env python scripts/cloud/test_delta_gcs.py
```

## Copy one Delta table from local object storage to GCS

The object storage (`minio` service) and PostgreSQL containers must be running when needed.

`--source-name` accepts `itviec`.

```powershell
uv run --env-file .env python -m scripts.cloud.migrate_minio_delta_to_gcs `
  --source-name itviec
```

If the destination already exists and should be replaced:

```powershell
uv run --env-file .env python -m scripts.cloud.migrate_minio_delta_to_gcs `
  --source-name itviec `
  --overwrite
```

## Export PostgreSQL tables to Parquet

`export_postgres_to_parquet.py` writes `silver.silver_jobs_unified`, `silver.fx_rates` and the
Gold dimensions, fact and bridge tables to `tmp/bigquery_export/<schema>/<table>.parquet` (the
`tmp/` folder is Git-ignored). It uses the PostgreSQL settings from `.env`, so the `postgres`
container must be running.

```powershell
uv run --env-file .env python -m scripts.cloud.export_postgres_to_parquet
```
