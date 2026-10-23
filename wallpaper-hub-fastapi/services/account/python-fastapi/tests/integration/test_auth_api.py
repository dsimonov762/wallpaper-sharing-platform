"""POST /auth/refresh and /auth/logout: the HTTP layer (needs the database, not Keycloak).

A recording stand-in plays the Keycloak token client, so these tests are about OUR contract:
public access, request validation, error shapes and headers. test_keycloak_auth.py talks to
the real Keycloak.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from account.domain.exceptions import ServiceUnavailableException, UnauthorizedException
from account.infra.keycloak_tokens import TokenSet

pytestmark = pytest.mark.integration

REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"


class FakeTokenClient:
    def __init__(self) -> None:
        self.refreshed: list[str] = []
        self.logged_out: list[str] = []
        self.error: Exception | None = None

    async def refresh(self, refresh_token: SecretStr) -> TokenSet:
        if self.error:
            raise self.error
        self.refreshed.append(refresh_token.get_secret_value())
        return TokenSet("new-access", "new-refresh", "Bearer", 299, 1799)

    async def logout(self, refresh_token: SecretStr) -> None:
        if self.error:
            raise self.error
        self.logged_out.append(refresh_token.get_secret_value())


@pytest.fixture
def tokens(client: TestClient) -> FakeTokenClient:
    fake = FakeTokenClient()
    client.app.state.token_client = fake  # type: ignore[attr-defined]
    return fake


def test_refresh_returns_the_new_tokens_and_forbids_caching(
    client: TestClient, tokens: FakeTokenClient
) -> None:
    response = client.post(REFRESH, json={"refreshToken": "old-refresh"})

    assert response.status_code == 200
    assert response.json() == {
        "accessToken": "new-access",
        "refreshToken": "new-refresh",
        "tokenType": "Bearer",
        "expiresIn": 299,
        "refreshExpiresIn": 1799,
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert tokens.refreshed == ["old-refresh"]


def test_both_endpoints_are_public_even_with_a_dead_access_token_attached(
    client: TestClient, tokens: FakeTokenClient
) -> None:
    expired = {"Authorization": "Bearer an.expired.token"}  # what a client holds when it refreshes

    assert client.post(REFRESH, json={"refreshToken": "r"}, headers=expired).status_code == 200
    assert client.post(LOGOUT, json={"refreshToken": "r"}, headers=expired).status_code == 204


def test_logout_answers_204_without_a_body(client: TestClient, tokens: FakeTokenClient) -> None:
    response = client.post(LOGOUT, json={"refreshToken": "old-refresh"})

    assert response.status_code == 204
    assert response.content == b""
    assert tokens.logged_out == ["old-refresh"]


@pytest.mark.parametrize("path", [REFRESH, LOGOUT])
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"refreshToken": ""},
        {"refreshToken": 123},
        {"refreshToken": None},
        {"refreshToken": "x" * 8193},
    ],
    ids=["missing", "empty", "number", "null", "too-long"],
)
def test_a_bad_request_body_is_a_400_that_never_echoes_the_token(
    client: TestClient, tokens: FakeTokenClient, path: str, body: dict[str, Any]
) -> None:
    response = client.post(path, json=body)

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["errors"][0]["field"] == "refreshToken"
    assert "x" * 50 not in response.text
    assert tokens.refreshed == tokens.logged_out == []


@pytest.mark.parametrize("path", [REFRESH, LOGOUT])
def test_an_invalid_refresh_token_is_a_401_problem(
    client: TestClient, tokens: FakeTokenClient, path: str
) -> None:
    tokens.error = UnauthorizedException("The refresh token is invalid or has expired.")

    response = client.post(path, json={"refreshToken": "whatever"})

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/unauthorized"
    assert "www-authenticate" not in response.headers  # not a Bearer-protected resource


@pytest.mark.parametrize("path", [REFRESH, LOGOUT])
def test_a_keycloak_outage_is_a_503_problem(
    client: TestClient, tokens: FakeTokenClient, path: str
) -> None:
    tokens.error = ServiceUnavailableException("Authentication is temporarily unavailable.")

    response = client.post(path, json={"refreshToken": "whatever"})

    assert response.status_code == 503
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/service-unavailable"


def test_the_endpoints_are_documented(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert "post" in paths[REFRESH]
    assert "post" in paths[LOGOUT]
    assert {"200", "400", "401"} <= set(paths[REFRESH]["post"]["responses"])
