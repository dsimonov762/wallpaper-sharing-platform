from fastapi import FastAPI
from fastapi.testclient import TestClient

from catalog.domain.exceptions import ServiceUnavailableException


class FakeDatabase:
    def __init__(self, up: bool) -> None:
        self.up = up

    async def ping(self) -> None:
        if not self.up:
            raise ServiceUnavailableException("The database is not reachable.")


def test_live_is_always_up(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_ready_is_up_when_database_answers(app: FastAPI, client: TestClient) -> None:
    app.state.database = FakeDatabase(up=True)
    assert client.get("/health/ready").status_code == 200


def test_ready_is_503_problem_when_database_is_down(app: FastAPI, client: TestClient) -> None:
    app.state.database = FakeDatabase(up=False)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/service-unavailable"
