import pytest
from pydantic import ValidationError

from account.config.settings import Settings


def test_defaults() -> None:
    settings = Settings()  # pyright: ignore[reportCallIssue]

    assert settings.service_name == "account-service"
    assert settings.db_pool_size == 5


def test_environment_variable_overrides_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCOUNT_ENVIRONMENT", "prod")
    monkeypatch.setenv("ACCOUNT_IDENTITY_PROVIDER", "keycloak")
    monkeypatch.setenv("ACCOUNT_KEYCLOAK_CLIENT_SECRET", "test-secret")

    assert Settings().environment == "prod"  # pyright: ignore[reportCallIssue]


def test_invalid_value_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ACCOUNT_ENVIRONMENT", "staging-ish")

    with pytest.raises(ValidationError):
        Settings()  # pyright: ignore[reportCallIssue]


def test_missing_database_url_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ACCOUNT_DATABASE_URL")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]  # ignore any local .env


def test_database_password_is_not_leaked_in_repr() -> None:
    assert "pw" not in repr(Settings())  # pyright: ignore[reportCallIssue]
