import os

from dotenv import load_dotenv

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from pathlib import Path

load_dotenv()

class Settings(BaseSettings):

    APP_NAME: str = "Recon API"

    # Set this in .env. PostgreSQL is the supported runtime database; SQLite
    # remains useful only when explicitly selected for isolated local tests.
    DATABASE_URL: str = "postgresql+psycopg2://recon:recon@localhost:5432/recon"

    SECRET_KEY: str

    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    CORS_ORIGINS: str = "https://insightful-adventure-production-169c.up.railway.app/"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    FRONTEND_URL: str = "https://insightful-adventure-production-169c.up.railway.app/"
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True
    ENVIRONMENT: str = "development"
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    PAYSTACK_SECRET_KEY: str | None = None
    PAYSTACK_PUBLIC_KEY: str | None = None
    PAYSTACK_PRO_PLAN_CODE: str | None = None
    PAYSTACK_PRO_ANNUAL_PLAN_CODE: str | None = None
    PAYSTACK_WEBHOOK_SECRET: str | None = None
    SUBSCRIPTION_GRACE_DAYS: int = 3

    DB_POOL_SIZE: int = Field(default=5, ge=1, le=50)
    DB_MAX_OVERFLOW: int = Field(default=2, ge=0, le=50)
    DB_POOL_TIMEOUT: int = Field(default=10, ge=1, le=60)
    MAX_FILE_BYTES: int = Field(default=100 * 1024 * 1024, ge=1024)
    MAX_SPREADSHEET_ROWS: int = Field(default=200_000, ge=1, le=1_000_000)
    MAX_SPREADSHEET_COLUMNS: int = Field(default=200, ge=1, le=1000)
    MAX_XLSX_EXPANDED_BYTES: int = Field(default=256 * 1024 * 1024, ge=1024)
    EXPORT_MAX_ROWS: int = Field(default=200_000, ge=1, le=1_000_000)
    EXPORT_MAX_BYTES: int = Field(default=100 * 1024 * 1024, ge=1024)
    EXPORT_TTL_HOURS: int = Field(default=24, ge=1, le=168)
    AUTH_RATE_LIMIT: int = Field(default=30, ge=1)
    LOGIN_ACCOUNT_LIMIT: int = Field(default=10, ge=1)
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str | None = None
    ENABLE_METRICS: bool = True

    RECONCILIATION_MODE: str = "sync"
    REDIS_URL: str | None = None

    STORAGE_BACKEND: str = "local"
    S3_BUCKET: str | None = None
    S3_REGION: str | None = None
    S3_PREFIX: str = "recon"
    S3_KMS_KEY_ID: str | None = None
    S3_ENDPOINT_URL: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_DEFAULT_REGION: str | None = None

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() in {"production", "prod"}

    @property
    def database_echo(self) -> bool:
        return not self.is_production

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = "postgresql+psycopg2://" + self.DATABASE_URL[len("postgres://"):]
        if os.getenv("RAILWAY_ENVIRONMENT_ID") and self.is_production and self.STORAGE_BACKEND != "s3":
            raise RuntimeError("Railway API and workers require shared S3 storage; set STORAGE_BACKEND=s3.")
        for name in ("S3_BUCKET", "S3_REGION", "S3_ENDPOINT_URL", "S3_KMS_KEY_ID", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION", "SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL", "PAYSTACK_SECRET_KEY", "PAYSTACK_PRO_PLAN_CODE", "PAYSTACK_PRO_ANNUAL_PLAN_CODE", "SENTRY_DSN"):
            if getattr(self, name) == "":
                setattr(self, name, None)
        if self.STORAGE_BACKEND not in {"local", "s3"}:
            raise RuntimeError("STORAGE_BACKEND must be local or s3.")
        if self.STORAGE_BACKEND == "s3" and not self.S3_BUCKET:
            raise RuntimeError("S3_BUCKET is required for shared storage.")
        if self.is_production and (len(self.SECRET_KEY) < 32 or "replace-with" in self.SECRET_KEY):
            raise RuntimeError("Production requires a random SECRET_KEY of at least 32 characters.")
        if self.is_production and (not self.FRONTEND_URL.startswith("https://") or not self.REDIS_URL):
            raise RuntimeError("Production requires HTTPS FRONTEND_URL and REDIS_URL.")
        if self.is_production and not self.SECRET_KEY:
            raise RuntimeError("SECRET_KEY must be set in production.")
        if self.is_production and self.SECRET_KEY == "dev-secret-key":
            raise RuntimeError("Refusing to start in production with the default SECRET_KEY.")


settings = Settings()


BASE_DIR = Path(__file__).resolve().parent.parent

UPLOAD_ROOT = BASE_DIR / "storage" / "uploads"

MAX_UPLOAD_SIZE = 100 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls"
}
