import pytest


@pytest.fixture(autouse=True)
def _hermetic_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests never touch a real database or read your local .env values."""
    monkeypatch.setenv("MEDIA_DATABASE_URL", "postgresql+asyncpg://user:pw@localhost:5432/unit")
    monkeypatch.setenv("MEDIA_ENVIRONMENT", "test")
