"""Typed application settings, loaded from environment variables."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Every setting can be overridden with an ACCOUNT_* environment variable.

    Example: ACCOUNT_ENVIRONMENT=prod. Values are validated when the object is created,
    so a typo in the environment stops the service at startup instead of failing later.
    Locally, put them in a `.env` file next to pyproject.toml (see `.env.example`).
    """

    model_config = SettingsConfigDict(env_prefix="ACCOUNT_", env_file=".env", extra="ignore")

    service_name: str = "account-service"
    environment: Literal["local", "test", "prod"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # No default on purpose: a missing database URL must stop the service at startup.
    # SecretStr hides the value in repr() and logs; read it with .get_secret_value().
    database_url: SecretStr
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_connect_timeout_s: float = Field(default=5.0, gt=0)

    oidc_issuer: str = "http://localhost:8180/realms/wallpaperhub"
    oidc_jwks_url: str | None = None  # None = issuer + /protocol/openid-connect/certs
    oidc_audience: str = "account-svc"
    oidc_leeway_seconds: int = 30
    oidc_jwks_ttl_seconds: int = 600
    oidc_jwks_min_refetch_seconds: int = 30

    # Which IdentityProvider creates the login behind a registration.
    # "local" invents ids (no Keycloak needed); "keycloak" calls Keycloak's admin API.
    identity_provider: Literal["local", "keycloak"] = "local"
    keycloak_base_url: str = "http://127.0.0.1:8180"
    keycloak_realm: str = "wallpaperhub"
    keycloak_client_id: str = "account-svc"
    keycloak_client_secret: SecretStr | None = None  # required when identity_provider=keycloak
    keycloak_timeout_s: float = Field(default=5.0, gt=0)

    @model_validator(mode="after")
    def _check_identity_provider(self) -> Self:
        if self.identity_provider == "keycloak" and self.keycloak_client_secret is None:
            raise ValueError("ACCOUNT_KEYCLOAK_CLIENT_SECRET is required for the keycloak provider")
        if self.environment == "prod" and self.identity_provider == "local":
            raise ValueError("the local identity provider must not be used when environment=prod")
        return self

    @property
    def jwks_url(self) -> str:
        return self.oidc_jwks_url or f"{self.oidc_issuer}/protocol/openid-connect/certs"
        # f"{self.keycloak_base_url}/realms/{self.keycloak_realm}/protocol/openid-connect/certs"


@lru_cache
def get_settings() -> Settings:
    """Create the settings once and reuse them."""
    return Settings()  # pyright: ignore[reportCallIssue]  # values come from the environment
