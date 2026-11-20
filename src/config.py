from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Nạp .env từ root project (nếu tồn tại).
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)


def _require(key: str) -> str:
    """Bắt buộc biến env phải tồn tại -- fail fast thay vì lỗi ngầm lúc connect."""
    value = os.environ.get(key)
    if not value:
        raise EnvironmentError(  # noqa: UP024
            f"Thieu bien moi truong bat buoc: {key}. Kiem tra file .env hoac "
            f"Airflow Variables/Connections."
        )
    return value


@dataclass(frozen=True)
class PostgresConfig:
    host: str
    port: int
    user: str
    password: str = field(repr=False)
    database: str

    @property
    def dsn(self) -> str:
        return (
            f"postgresql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @classmethod
    def from_env(cls) -> "PostgresConfig":  # noqa: UP037
        return cls(
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            user=_require("POSTGRES_USER"),
            password=_require("POSTGRES_PASSWORD"),
            database=os.environ.get("POSTGRES_DB", "it_jobs_dw"),
        )


@dataclass(frozen=True)
class MinioConfig:
    endpoint_url: str
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    bucket: str
    region: str = "us-east-1"
    allow_http: bool = True

    @property
    def storage_options(self) -> dict[str, str]:
        """Cấu hình kết nối S3 truyền thẳng vào write_deltalake() / DeltaTable() của delta-rs."""
        return {
            "AWS_ENDPOINT_URL": self.endpoint_url,
            "AWS_ACCESS_KEY_ID": self.access_key,
            "AWS_SECRET_ACCESS_KEY": self.secret_key,
            "AWS_REGION": self.region,
            "AWS_ALLOW_HTTP": "true" if self.allow_http else "false",
        }

    def table_uri(self, path: str) -> str:
        """path vd: 'bronze/itviec' -> s3://<bucket>/bronze/itviec"""
        return f"s3://{self.bucket}/{path.strip('/')}"

    @classmethod
    def from_env(cls) -> "MinioConfig":  # noqa: UP037
        return cls(
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:9000"),
            access_key=_require("AWS_ACCESS_KEY_ID"),
            secret_key=_require("AWS_SECRET_ACCESS_KEY"),
            bucket=os.environ.get("MINIO_BUCKET", "it-jobs-lakehouse"),
            region=os.environ.get("AWS_REGION", "us-east-1"),
            allow_http=os.environ.get("AWS_ALLOW_HTTP", "true").lower() == "true",
        )


@dataclass(frozen=True)
class GcsConfig:
    bucket: str

    @property
    def storage_options(self) -> dict[str, str]:
        return {}

    def table_uri(self, path: str) -> str:
        return f"gs://{self.bucket}/{path.strip('/')}"

    @classmethod
    def from_env(cls) -> "GcsConfig":  # noqa: UP037
        return cls(
            bucket=os.environ.get(
                "GCS_BUCKET",
                "it-jobs-lakehouse",
            ),
        )


# Singleton-style accessors.
def get_postgres_config() -> PostgresConfig:
    return PostgresConfig.from_env()


def get_minio_config() -> MinioConfig:
    return MinioConfig.from_env()


def get_gcs_config() -> GcsConfig:
    return GcsConfig.from_env()
