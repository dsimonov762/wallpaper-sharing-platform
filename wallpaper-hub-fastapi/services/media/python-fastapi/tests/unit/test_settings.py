import pytest
from pydantic import ValidationError

from media.config.settings import Settings, get_settings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEDIA_DATABASE_URL")

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert "database_url" in str(error.value)


def test_values_come_from_media_prefixed_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_DB_POOL_SIZE", "7")
    monkeypatch.setenv("MEDIA_LOG_LEVEL", "DEBUG")

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.db_pool_size == 7
    assert settings.log_level == "DEBUG"
    assert settings.service_name == "media-service"


def test_account_prefixed_variables_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    # Both services may share one shell: the prefix keeps their settings apart.
    monkeypatch.setenv("ACCOUNT_DB_POOL_SIZE", "42")

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert settings.db_pool_size == 5


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_ENVIRONMENT", "staging")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]


def test_database_url_is_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEDIA_DATABASE_URL", "postgresql+asyncpg://u:top-secret@localhost/db")

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]

    assert "top-secret" not in repr(settings)
    assert "top-secret" in settings.database_url.get_secret_value()


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()

    assert get_settings() is get_settings()

    get_settings.cache_clear()
