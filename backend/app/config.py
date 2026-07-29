from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://fitness:fitness@localhost:5432/fitness"
    test_database_url: str = "postgresql+asyncpg://fitness:fitness@localhost:5432/fitness_test"

    jwt_secret: str = "dev-only-change-me-not-for-production-use"
    jwt_ttl_seconds: int = 86400

    cv_service_url: str = "http://localhost:9000"
    cv_api_key: str = "dev-cv-api-key"
    cv_webhook_secret: str = "dev-webhook-secret-change-me-in-production"
    webhook_tolerance_sec: int = 300
    backend_public_url: str = "http://localhost:8000"

    storage_dir: Path = Path("./var/videos")

    max_upload_bytes: int = 104_857_600
    max_duration_sec: int = 60

    retention_days: int = 30

    cv_poll_after_sec: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
