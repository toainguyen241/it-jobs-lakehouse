from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow import DAG  # type: ignore
from airflow.operators.bash import BashOperator  # type: ignore
from telegram_alerts import notify_task_failure, notify_task_retry

PROJECT_DIR = "/opt/airflow"
DBT_DIR = f"{PROJECT_DIR}/transform_dbt"
PIPELINE_BIN = f"{PROJECT_DIR}/pipeline_venv/bin"


def crawl_result_env(crawl_task_id: str) -> dict[str, str]:
    """Render crawler XCom into an environment variable, not shell source."""
    return {
        "CRAWL_RESULT": f"{{{{ ti.xcom_pull(task_ids='{crawl_task_id}') }}}}",
    }


def load_from_xcom_command(source_name: str) -> str:
    """Load Bronze bằng path Parquet lấy trực tiếp từ XCom của task crawl tương ứng (dòng cuối cùng crawl in ra stdout: "PARQUET_PATH=<path>" hoặc sentinel "NO_NEW_JOBS" nếu crawler không tìm thấy job mới nào)."""
    return f"""
set -euo pipefail
RAW="${{CRAWL_RESULT:-}}"

if [ "$RAW" = "NO_NEW_JOBS" ]; then
    echo "[{source_name}] Không có job mới từ crawl task -- skip load Bronze."
    exit 0
fi

case "$RAW" in
    PARQUET_PATH=*) PARQUET_PATH="${{RAW#PARQUET_PATH=}}" ;;
    *)
        echo "[{source_name}] XCom không hợp lệ: $RAW" >&2
        exit 1
        ;;
esac

if [ -z "$PARQUET_PATH" ]; then
    echo "[{source_name}] PARQUET_PATH rỗng." >&2
    exit 1
fi

if [ ! -f "$PARQUET_PATH" ]; then
    echo "[{source_name}] File không tồn tại: $PARQUET_PATH" >&2
    exit 1
fi

{PIPELINE_BIN}/python -m src.load_bronze_crawled \
  --parquet-path "$PARQUET_PATH" \
  --source-name {source_name}
"""


default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=10),
    "on_retry_callback": notify_task_retry,
    "on_failure_callback": notify_task_failure,
}


with DAG(
    dag_id="it_jobs_lakehouse",
    description="Crawl jobs, load Bronze, and build/test dbt Silver and Gold layers.",
    is_paused_upon_creation=False,
    schedule="0 2 * * *",
    start_date=pendulum.datetime(2026, 8, 1, tz="Asia/Bangkok"),
    catchup=False,
    max_active_runs=1,  # type: ignore
    dagrun_timeout=timedelta(hours=6),  # type: ignore
    default_args=default_args,  # type: ignore
    tags=["it-jobs", "lakehouse"],
) as dag:
    crawl_itviec = BashOperator(
        task_id="crawl_itviec",
        bash_command=(
            f"cd {PROJECT_DIR} && {PIPELINE_BIN}/python crawl_itviec.py --max-pages 7"
        ),
        do_xcom_push=True,
        execution_timeout=timedelta(hours=1),
    )

    load_bronze_itviec = BashOperator(
        task_id="load_bronze_itviec",
        bash_command=load_from_xcom_command("itviec"),
        env=crawl_result_env("crawl_itviec"),
        append_env=True,
        cwd=PROJECT_DIR,
    )

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command=f"{PIPELINE_BIN}/dbt seed --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
        cwd=PROJECT_DIR,
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=f"{PIPELINE_BIN}/dbt run --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
        cwd=PROJECT_DIR,
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=f"{PIPELINE_BIN}/dbt test --project-dir {DBT_DIR} --profiles-dir {DBT_DIR}",
        cwd=PROJECT_DIR,
    )

    publish_marts_to_supabase = BashOperator(
        task_id="publish_marts_to_supabase",
        bash_command=f"""
set -euo pipefail
if [ -z "${{SUPABASE_DB_URL:-}}" ]; then
    echo "SUPABASE_DB_URL is not configured; skip Supabase mart publish."
    exit 99
fi
{PIPELINE_BIN}/python {PROJECT_DIR}/scripts/publish_marts_to_supabase.py
""",
        cwd=PROJECT_DIR,
        skip_on_exit_code=99,
        execution_timeout=timedelta(minutes=30),
    )

    crawl_itviec >> load_bronze_itviec  # type: ignore
    load_bronze_itviec >> dbt_seed  # type: ignore
    dbt_seed >> dbt_run >> dbt_test >> publish_marts_to_supabase  # type: ignore
