"""Typed application settings, loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting can be overridden with a MEDIA_* environment variable.

    Example: MEDIA_ENVIRONMENT=prod. Values are validated when the object is created,
    so a typo in the environment stops the service at startup instead of failing later.
    Locally, put them in a `.env` file next to pyproject.toml (see `.env.example`).
    """

    model_config = SettingsConfigDict(env_prefix="MEDIA_", env_file=".env", extra="ignore")

    service_name: str = "media-service"
    environment: Literal["local", "test", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # No default on purpose: a missing database URL must stop the service at startup.
    # SecretStr hides the value in repr() and logs; read it with .get_secret_value().
    database_url: SecretStr
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_connect_timeout_s: float = Field(default=5.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    """Create the settings once and reuse them."""
    return Settings()  # pyright: ignore[reportCallIssue]  # values come from the environment
