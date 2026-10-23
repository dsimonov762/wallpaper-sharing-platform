"""/auth/refresh and /auth/logout against a REAL Keycloak (needs `just infra-up` and the database).
Skipped automatically when Keycloak is not running. Uses the demo user `alice` from the realm."""

from typing import Any
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

KEYCLOAK = "http://127.0.0.1:8180"
REALM = "wallpaperhub"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"


@pytest.fixture(scope="module", autouse=True)
def keycloak_is_ready() -> None:
    try:
        httpx2.get(f"{KEYCLOAK}/realms/{REALM}/.well-known/openid-configuration", timeout=2.0)
    except httpx2.HTTPError:
        pytest.skip("Keycloak is not running on localhost:8180 (just infra-up)")


def log_in_as_alice() -> dict[str, Any]:
    response = httpx2.post(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "dev-tools",
            "username": "alice",
            "password": "alice123",
        },
        timeout=5.0,
    )
    assert response.status_code == 200
    return response.json()


def is_accepted(client: TestClient, access_token: str) -> bool:
    """The API answers 404 for an unknown user id, but only if the token was accepted first."""
    response = client.get(
        f"/api/v1/users/{uuid4()}", headers={"Authorization": f"Bearer {access_token}"}
    )
    return response.status_code == 404


def test_a_refreshed_access_token_is_accepted_by_the_api(client: TestClient) -> None:
    login = log_in_as_alice()

    response = client.post(REFRESH, json={"refreshToken": login["refresh_token"]})

    body = response.json()
    assert response.status_code == 200
    assert body["accessToken"] != login["access_token"]
    assert body["tokenType"] == "Bearer"
    assert body["expiresIn"] > 0
    assert is_accepted(client, body["accessToken"])
    # the new refresh token works too, so a client can keep going indefinitely
    assert client.post(REFRESH, json={"refreshToken": body["refreshToken"]}).status_code == 200


def test_logout_ends_the_session_so_the_token_stops_working(client: TestClient) -> None:
    refresh_token = log_in_as_alice()["refresh_token"]
    assert client.post(REFRESH, json={"refreshToken": refresh_token}).status_code == 200

    assert client.post(LOGOUT, json={"refreshToken": refresh_token}).status_code == 204

    after = client.post(REFRESH, json={"refreshToken": refresh_token})
    assert after.status_code == 401
    assert after.headers["content-type"] == "application/problem+json"
    assert (
        client.post(LOGOUT, json={"refreshToken": refresh_token}).status_code == 204
    )  # repeat: ok


@pytest.mark.parametrize("path", [REFRESH, LOGOUT])
def test_junk_and_access_tokens_are_refused_as_refresh_tokens(
    client: TestClient, path: str
) -> None:
    access_token = log_in_as_alice()["access_token"]

    for token in ("garbage", access_token):
        response = client.post(path, json={"refreshToken": token})
        assert response.status_code == 401
        assert response.json()["detail"] == "The refresh token is invalid or has expired."
