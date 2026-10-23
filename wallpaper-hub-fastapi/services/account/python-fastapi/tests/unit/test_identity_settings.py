"""The settings that choose the identity provider fail fast on bad combinations."""

import pytest
from pydantic import SecretStr, ValidationError

from account.config.settings import Settings

DATABASE = SecretStr("postgresql+asyncpg://user:pw@localhost/db")


def settings(**values: object) -> Settings:
    # _env_file=None: ignore a developer's .env so the test depends only on its own values
    return Settings(database_url=DATABASE, _env_file=None, **values)  # type: ignore[arg-type]


def test_local_is_the_default_provider() -> None:
    assert settings().identity_provider == "local"


def test_keycloak_provider_needs_a_client_secret() -> None:
    with pytest.raises(ValidationError, match="KEYCLOAK_CLIENT_SECRET"):
        settings(identity_provider="keycloak")


def test_keycloak_provider_with_a_secret_is_valid() -> None:
    config = settings(identity_provider="keycloak", keycloak_client_secret=SecretStr("s3cret"))

    assert config.keycloak_realm == "wallpaperhub"
    assert "s3cret" not in repr(config)


def test_the_local_provider_is_refused_in_production() -> None:
    with pytest.raises(ValidationError, match="prod"):
        settings(environment="prod", identity_provider="local")


def test_production_with_keycloak_is_fine() -> None:
    config = settings(
        environment="prod", identity_provider="keycloak", keycloak_client_secret=SecretStr("x")
    )

    assert config.identity_provider == "keycloak"
