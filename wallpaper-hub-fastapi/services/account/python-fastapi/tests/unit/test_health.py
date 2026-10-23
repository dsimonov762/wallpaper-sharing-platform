import pytest
from fastapi.testclient import TestClient

from account.main import create_app


def test_live_returns_up() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_ready_is_up_when_database_is_reachable(monkeypatch: pytest.MonkeyPatch) -> None:
    async def reachable(_engine: object) -> bool:
        return True

    monkeypatch.setattr("account.api.http.health.database_is_reachable", reachable)

    with TestClient(create_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "checks": {"database": "UP"}}


def test_ready_is_503_when_database_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def unreachable(_engine: object) -> bool:
        return False

    monkeypatch.setattr("account.api.http.health.database_is_reachable", unreachable)

    with TestClient(create_app()) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "DOWN"
