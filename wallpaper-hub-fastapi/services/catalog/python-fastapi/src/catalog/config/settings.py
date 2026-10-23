"""Typed, validated configuration. Environment variables use the prefix CATALOG_."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CATALOG_", env_file=".env", extra="ignore")

    environment: Literal["local", "test", "prod"] = "local"

    # No default on purpose: the service must not start without knowing its database.
    mongodb_uri: SecretStr
    mongodb_database: str = "catalog"
    mongodb_server_selection_timeout_ms: int = 2000

    # Who resolves author snapshots. Only the stand-in exists until step C5 adds "grpc".
    author_directory: Literal["local"] = "local"

    @model_validator(mode="after")
    def _refuse_stand_ins_in_prod(self) -> Self:
        if self.environment == "prod" and self.author_directory == "local":
            msg = "author_directory=local is a development stand-in and is refused in prod"
            raise ValueError(msg)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
