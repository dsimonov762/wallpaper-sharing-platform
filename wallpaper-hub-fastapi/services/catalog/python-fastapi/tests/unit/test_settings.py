import pytest
from pydantic import ValidationError

from catalog.config.settings import Settings


def test_database_uri_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CATALOG_MONGODB_URI")
    with pytest.raises(ValidationError) as info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert "mongodb_uri" in str(info.value)


def test_stand_in_author_directory_is_refused_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOG_ENVIRONMENT", "prod")
    with pytest.raises(ValidationError) as info:
        Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert "refused in prod" in str(info.value)


def test_uri_is_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATALOG_MONGODB_URI", "mongodb://u:topsecret@h:27017/catalog")
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert "topsecret" not in repr(settings)
    assert settings.mongodb_database == "catalog"
