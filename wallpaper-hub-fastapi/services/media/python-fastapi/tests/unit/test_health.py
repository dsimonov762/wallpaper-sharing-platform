from http import HTTPStatus
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine

from media.api.http.dependencies import get_engine
from media.main import create_app


def _client(monkeypatch: pytest.MonkeyPatch, *, database_up: bool) -> TestClient:
    """An app whose database check is faked: no real Postgres is needed."""

    async def fake_database_is_reachable(_engine: AsyncEngine) -> bool:
        return database_up

    monkeypatch.setattr("media.api.http.health.database_is_reachable", fake_database_is_reachable)
    app = create_app()
    # The lifespan is not started here (no `with TestClient`), so there is no real engine.
    app.dependency_overrides[get_engine] = lambda: cast(AsyncEngine, object())
    return TestClient(app)


def test_live_is_up(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _client(monkeypatch, database_up=False).get("/health/live")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "UP"}  # liveness never looks at the database


def test_ready_is_up_when_database_is_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _client(monkeypatch, database_up=True).get("/health/ready")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "UP", "checks": {"postgres": "UP"}}


def test_ready_is_503_when_database_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    response = _client(monkeypatch, database_up=False).get("/health/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json() == {"status": "DOWN", "checks": {"postgres": "DOWN"}}
