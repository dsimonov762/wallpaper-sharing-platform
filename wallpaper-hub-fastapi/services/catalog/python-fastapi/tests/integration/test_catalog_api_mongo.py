"""The whole service (HTTP -> service -> repository) against a real MongoDB."""

import pytest
from fastapi.testclient import TestClient

from catalog.config.settings import Settings
from catalog.main import create_app

pytestmark = pytest.mark.integration

URL = "/api/v1/wallpapers"
BODY = {
    "title": "Misty Pines",
    "description": "Fog over a pine forest",
    "tags": ["forest", "fog"],
    "category": "NATURE",
    "assetId": "ast_01HXABCDEFGH",
    "authorId": "u-alice",
}


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as test_client:
        return test_client


def test_ready_is_up_with_a_real_database(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/health/ready").status_code == 200


def test_ready_is_503_when_mongodb_is_unreachable(settings: Settings) -> None:
    unreachable = settings.model_copy(
        update={
            "mongodb_uri": type(settings.mongodb_uri)("mongodb://127.0.0.1:1/catalog"),
            "mongodb_server_selection_timeout_ms": 300,
        }
    )
    with TestClient(create_app(unreachable)) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["type"].endswith("/service-unavailable")


def test_create_read_update_list_flow(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        created = client.post(URL, json=BODY)
        assert created.status_code == 201
        wallpaper_id = created.json()["id"]
        assert wallpaper_id.startswith("wp_")
        assert len(wallpaper_id) == 29  # "wp_" + 26-character ULID

        fetched = client.get(f"{URL}/{wallpaper_id}")
        assert fetched.json() == created.json()
        assert fetched.headers["etag"] == '"1"'

        patched = client.patch(
            f"{URL}/{wallpaper_id}", json={"title": "Misty Pines II"}, headers={"If-Match": '"1"'}
        )
        assert patched.status_code == 200
        assert (patched.json()["title"], patched.json()["version"]) == ("Misty Pines II", 2)

        stale = client.patch(
            f"{URL}/{wallpaper_id}", json={"title": "Late"}, headers={"If-Match": '"1"'}
        )
        assert stale.status_code == 412

        listing = client.get(URL, params={"tag": "fog", "authorId": "u-alice"}).json()
        assert listing["totalItems"] == 1
        assert listing["items"][0]["title"] == "Misty Pines II"


def test_dates_survive_the_database_as_utc_iso_strings(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        created = client.post(URL, json=BODY).json()
        fetched = client.get(f"{URL}/{created['id']}").json()
    assert fetched["createdAt"] == created["createdAt"]
    assert fetched["createdAt"].endswith("Z")
