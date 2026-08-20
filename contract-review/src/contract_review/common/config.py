from dataclasses import dataclass
from os import getenv

from pydantic_settings import BaseSettings


class ProductionGateError(RuntimeError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass(frozen=True)
class DatabaseSettings:
    """PostgreSQL connection settings. Used when DATABASE_URL points to postgresql."""

    url: str = "postgresql+psycopg://contract:contract@127.0.0.1:5432/contract_review"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10

    @classmethod
    def from_env(cls) -> "DatabaseSettings":
        return cls(
            url=getenv("DATABASE_URL", cls.url),
            echo=getenv("DB_ECHO", "false").lower() in {"1", "true", "yes"},
            pool_size=int(getenv("DB_POOL_SIZE", str(cls.pool_size))),
            max_overflow=int(getenv("DB_MAX_OVERFLOW", str(cls.max_overflow))),
        )

    @property
    def is_postgres(self) -> bool:
        return "postgresql" in self.url

    @property
    def is_configured(self) -> bool:
        return bool(self.url) and self.is_postgres


@dataclass(frozen=True)
class MinioSettings:
    endpoint: str = "127.0.0.1:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "contract-review"
    secure: bool = False

    @classmethod
    def from_env(cls) -> "MinioSettings":
        return cls(
            endpoint=getenv("MINIO_ENDPOINT", cls.endpoint),
            access_key=getenv("MINIO_ACCESS_KEY", cls.access_key),
            secret_key=getenv("MINIO_SECRET_KEY", cls.secret_key),
            bucket=getenv("MINIO_BUCKET_NAME", cls.bucket),
            secure=getenv("MINIO_SECURE", str(cls.secure)).lower() in {"1", "true", "yes"},
        )

    @property
    def url(self) -> str:
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.endpoint}"


class Settings(BaseSettings):
    """应用级配置。demo 模式保持零配置可运行；production 由门禁强制约束。"""

    environment: str = "local"  # local | production
    demo_mode: bool = True
    auth_enabled: bool = False
    storage_backend: str = "memory"  # memory | minio | postgres

    database_url: str = "sqlite:///./data/contract_review.db"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174"
    max_upload_size_mb: int = 10

    session_ttl_seconds: int = 8 * 60 * 60
    session_secret: str = "dev-session-secret-change-me"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


def load_settings() -> Settings:
    return Settings(
        environment=getenv("ENVIRONMENT", "local"),
        demo_mode=getenv("DEMO_MODE", "true").lower() in {"1", "true", "yes"},
        auth_enabled=getenv("AUTH_ENABLED", "false").lower() in {"1", "true", "yes"},
        storage_backend=getenv("STORAGE_BACKEND", "memory").lower(),
        database_url=getenv("DATABASE_URL", "sqlite:///./data/contract_review.db"),
        cors_origins=getenv("CORS_ORIGINS", ""),
        max_upload_size_mb=int(getenv("MAX_UPLOAD_SIZE_MB", "10")),
        session_ttl_seconds=int(getenv("SESSION_TTL_SECONDS", str(8 * 60 * 60))),
        session_secret=getenv("SESSION_SECRET", "dev-session-secret-change-me"),
    )


def validate_production_settings(settings: Settings) -> None:
    """生产启动门禁：任一约束不满足则拒绝启动。"""
    if settings.environment != "production":
        return
    if settings.demo_mode:
        raise ProductionGateError("ENVIRONMENT=production 时 DEMO_MODE 必须为 false")
    if not settings.auth_enabled:
        raise ProductionGateError("ENVIRONMENT=production 时 AUTH_ENABLED 必须为 true")
    if settings.storage_backend not in ("minio", "postgres"):
        raise ProductionGateError("ENVIRONMENT=production 时 STORAGE_BACKEND 必须为 minio 或 postgres")
    if not settings.database_url.startswith("postgresql"):
        raise ProductionGateError("ENVIRONMENT=production 时 DATABASE_URL 必须为 PostgreSQL")
    if settings.session_secret == "dev-session-secret-change-me":
        raise ProductionGateError("ENVIRONMENT=production 时必须配置 SESSION_SECRET")
    if settings.cors_origins in {"", "*"}:
        raise ProductionGateError("ENVIRONMENT=production 时 CORS_ORIGINS 必须为具体来源")
