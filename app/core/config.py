"""Application configuration settings."""

from functools import lru_cache
from typing import Any

from pydantic import field_validator, model_validator
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
    cors_origins: list[str] = [
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]

    database_url: str = "postgresql+psycopg://auditlens:auditlens_password@localhost:5432/auditlens"

    jwt_secret: str = "replace_with_a_secure_random_secret_at_least_32_chars"
    jwt_expire_minutes: int = 60

    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "change_this_admin_password"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from comma-separated string, JSON list, or collection."""
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                import json

                try:
                    return json.loads(v_str)
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return v

    @model_validator(mode="after")
    def validate_production_jwt_secret(self) -> "Settings":
        """Refuse to start in production mode if JWT secret is default placeholder or insecure."""
        if self.app_env.lower() == "production":
            if (
                self.jwt_secret == "replace_with_a_secure_random_secret_at_least_32_chars"
                or len(self.jwt_secret) < 32
            ):
                raise ValueError(
                    "Production mode requires a secure JWT_SECRET with at least 32 characters. "
                    "Cannot use the default placeholder secret."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
