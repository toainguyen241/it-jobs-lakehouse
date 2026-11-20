from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".uv-cache",
    ".ruff_cache",
    "__pycache__",
    "browser_profile",
    "context",
    "crawl",
    "data",
    "dbt_packages",
    "htmlcov",
    "logs",
    "storage_state",
    "target",
    "tmp",
}
EXCLUDED_FILES = {".env"}
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".csv",
    ".dockerignore",
    ".env",
    ".example",
    ".html",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
PATTERNS = {
    "telegram_bot_token": re.compile(r"\b\d{8,12}:AA[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(
        r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}\b"
        r"|\bgithub_pat_[A-Za-z0-9_]{40,}\b"
    ),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def candidate_files():
    for directory, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIRS]
        base = Path(directory)
        for filename in filenames:
            if filename in EXCLUDED_FILES:
                continue
            path = base / filename
            if path.suffix.lower() in TEXT_SUFFIXES or path.name.startswith("."):
                yield path


def main() -> int:
    findings: list[tuple[str, int, str]] = []
    for path in candidate_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for category, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append(
                        (path.relative_to(ROOT).as_posix(), line_number, category)
                    )

    if findings:
        print("Potential secrets found (values intentionally hidden):")
        for path, line_number, category in findings:
            print(f"- {path}:{line_number} [{category}]")
        return 1

    print("Secret scan passed: không phát hiện dữ liệu nhạy cảm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
