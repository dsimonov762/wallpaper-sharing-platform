from fastapi.testclient import TestClient

from catalog.config.settings import Settings
from catalog.main import create_app


def test_app_starts_and_stops_without_a_reachable_database() -> None:
    """The Mongo client connects lazily, so startup must not need MongoDB (README: fail on use)."""
    app = create_app(Settings())  # pyright: ignore[reportCallIssue]
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        assert app.state.database is not None


def test_openapi_documents_problem_responses() -> None:
    app = create_app(Settings())  # pyright: ignore[reportCallIssue]
    with TestClient(app) as client:
        spec = client.get("/openapi.json").json()
    patch = spec["paths"]["/api/v1/wallpapers/{wallpaper_id}"]["patch"]
    assert {"412", "428", "404", "400"} <= set(patch["responses"])
