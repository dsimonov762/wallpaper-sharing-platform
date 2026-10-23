"""Typed, validated configuration (12-factor: environment variables plus an optional .env file)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The .env file lives next to pyproject.toml, wherever the process is started from.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

_REDIS_SCHEMES = ("redis://", "rediss://", "unix://")


class Settings(BaseSettings):
    """Every value can be set with an environment variable prefixed NOTIFICATION_."""

    model_config = SettingsConfigDict(
        env_prefix="NOTIFICATION_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["local", "test", "prod"] = "local"

    # Required, no default: the service refuses to start without it (fail fast).
    # SecretStr keeps a password inside the URL out of logs and repr().
    redis_url: SecretStr

    redis_connect_timeout_seconds: float = Field(default=1.0, gt=0)
    redis_command_timeout_seconds: float = Field(default=2.0, gt=0)
    health_check_timeout_seconds: float = Field(default=1.0, gt=0)

    @field_validator("redis_url")
    @classmethod
    def _check_redis_scheme(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().startswith(_REDIS_SCHEMES):
            raise ValueError("must start with redis://, rediss:// or unix://")
        return value


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""
    return Settings()  # pyright: ignore[reportCallIssue]
