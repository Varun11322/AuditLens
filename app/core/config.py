"""Application configuration settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    api_base_url: str = "http://localhost:8000"
    max_upload_mb: int = 25

    database_url: str = "postgresql+psycopg://auditlens:auditlens_password@localhost:5432/auditlens"

    jwt_secret: str = "replace_with_a_secure_random_secret_at_least_32_chars"
    jwt_expire_minutes: int = 60

    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "change_this_admin_password"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
