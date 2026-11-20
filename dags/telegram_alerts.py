from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOGGER = logging.getLogger(__name__)
TELEGRAM_API_ROOT = "https://api.telegram.org"
MAX_ERROR_LENGTH = 1_500
NETWORK_RETRY_DELAYS = (5, 15)
DEFAULT_DBT_RUN_RESULTS_PATH = Path(
    "/opt/airflow/transform_dbt/target/run_results.json"
)


def _redact(value: object) -> str:
    text = str(value or "Unknown error")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if token:
        text = text.replace(token, "[REDACTED]")
    text = re.sub(r"://[^\s:/]+:[^\s@]+@", "://[REDACTED]@", text)
    text = re.sub(
        r"(?i)\b(password|token|secret|api[_-]?key)\s*[=:]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        text,
    )
    return text[:MAX_ERROR_LENGTH]


def _dbt_failure_summary(task_instance: object) -> str | None:
    """Return current dbt failing node names without leaking artifact payloads."""
    task_id = str(getattr(task_instance, "task_id", ""))
    if not task_id.startswith("dbt_"):
        return None

    path = Path(os.getenv("DBT_RUN_RESULTS_PATH", str(DEFAULT_DBT_RUN_RESULTS_PATH)))
    try:
        start_date = getattr(task_instance, "start_date", None)
        if start_date is not None and path.stat().st_mtime < start_date.timestamp() - 5:
            return None

        artifact = json.loads(path.read_text(encoding="utf-8"))
        failures = [
            str(result.get("unique_id", "unknown")).rsplit(".", 1)[-1]
            for result in artifact.get("results", [])
            if result.get("status") in {"error", "fail"}
        ]
    except (OSError, ValueError, TypeError, AttributeError):
        return None

    if not failures:
        return None
    visible = failures[:5]
    suffix = f" (+{len(failures) - len(visible)} more)" if len(failures) > 5 else ""
    return _redact(", ".join(visible) + suffix)


def build_alert_message(context: dict[str, Any], status: str) -> str:
    """Build a compact plain-text alert without exposing configured secrets."""
    task_instance = context.get("task_instance") or context.get("ti")
    dag_run = context.get("dag_run")
    dag_id = getattr(task_instance, "dag_id", None) or context.get("dag_id", "unknown")
    task_id = getattr(task_instance, "task_id", None) or "unknown"
    run_id = getattr(dag_run, "run_id", None) or getattr(
        task_instance, "run_id", "unknown"
    )
    log_url = getattr(task_instance, "log_url", None)
    try_number = getattr(task_instance, "try_number", None)

    lines = [
        f"AIRFLOW TASK {status}",
        f"DAG: {dag_id}",
        f"Task: {task_id}",
        f"Run: {run_id}",
    ]
    if try_number is not None:
        lines.append(f"Try: {try_number}")
    dbt_failure_summary = _dbt_failure_summary(task_instance)
    if dbt_failure_summary:
        lines.append(f"dbt failures: {dbt_failure_summary}")
    lines.append(f"Error: {_redact(context.get('exception'))}")
    if log_url:
        lines.append(f"Log: {log_url}")
    return "\n".join(lines)


def build_failure_message(context: dict[str, Any]) -> str:
    """Backward-compatible helper for terminal failure messages."""
    return build_alert_message(context, "FAILED")


def send_telegram_message(message: str) -> bool:
    """Send an alert; notification errors must not break the scheduler."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        LOGGER.warning(
            "Telegram alert skipped: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing"
        )
        return False

    request = Request(
        f"{TELEGRAM_API_ROOT}/bot{token}/sendMessage",
        data=json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    for attempt in range(len(NETWORK_RETRY_DELAYS) + 1):
        try:
            with urlopen(request, timeout=10) as response:
                return 200 <= response.status < 300
        except HTTPError as exc:
            if exc.code != 429 and exc.code < 500:
                LOGGER.error("Telegram alert failed (HTTP %s)", exc.code)
                return False
            error: Exception = exc
        except (URLError, TimeoutError, OSError) as exc:
            error = exc

        if attempt == len(NETWORK_RETRY_DELAYS):
            LOGGER.error("Telegram alert failed (%s)", type(error).__name__)
            return False
        delay = NETWORK_RETRY_DELAYS[attempt]
        LOGGER.warning(
            "Telegram alert network failure (%s); retry in %ss",
            type(error).__name__,
            delay,
        )
        time.sleep(delay)
    return False


def notify_task_failure(context: dict[str, Any]) -> None:
    """Airflow callback invoked only after a task exhausts its retries."""
    send_telegram_message(build_alert_message(context, "FAILED"))


def notify_task_retry(context: dict[str, Any]) -> None:
    """Airflow callback invoked when a failed attempt is waiting to retry."""
    send_telegram_message(build_alert_message(context, "UP FOR RETRY"))
