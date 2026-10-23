"""The `get_current_user` dependency, tested through a tiny throw-away app.

No real route is protected yet (that is step 3.4), so this test app has one route,
`/whoami`, that simply returns the CurrentUser. Keys come from a fake JWKS.
"""

import asyncio
import json
import time
from collections.abc import Iterator, Mapping
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from account.api.http.dependencies import CurrentUserDep
from account.api.http.errors import register_exception_handlers
from account.security.errors import JwksUnavailableError
from account.security.jwks import JwksCache
from account.security.jwt_validator import TokenValidator

ISSUER = "http://localhost:8180/realms/wallpaperhub"
AUDIENCE = "account-svc"
PROBLEM = "application/problem+json"
KID = "test-key"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Keys:
    """Fake JWKS endpoint; flip `down` to simulate a Keycloak outage."""

    down = False

    async def __call__(self) -> Mapping[str, object]:
        await asyncio.sleep(0)
        if self.down:
            raise JwksUnavailableError("down")
        jwk = json.loads(RSAAlgorithm.to_jwk(_private_key.public_key()))
        jwk.update({"kid": KID, "use": "sig", "alg": "RS256"})
        return {"keys": [jwk]}


def make_token(**overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "user-1",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "typ": "Bearer",
        "exp": now + 300,
        "email": "alice@example.com",
        "realm_access": {"roles": ["USER"]},
        **overrides,
    }
    return jwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": KID})


@pytest.fixture
def keys() -> Keys:
    return Keys()


@pytest.fixture
def client(keys: Keys) -> Iterator[TestClient]:
    app = FastAPI()
    register_exception_handlers(app)
    app.state.token_validator = TokenValidator(
        JwksCache(keys), issuer=ISSUER, audience=AUDIENCE, leeway_seconds=30
    )

    @app.get("/whoami")
    async def whoami(user: CurrentUserDep) -> dict[str, Any]:
        return {"id": user.id, "email": user.email, "roles": sorted(user.roles)}

    with TestClient(app) as test_client:
        yield test_client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_valid_token_identifies_the_caller(client: TestClient) -> None:
    response = client.get("/whoami", headers=bearer(make_token()))
    assert response.status_code == 200
    assert response.json() == {"id": "user-1", "email": "alice@example.com", "roles": ["USER"]}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic YWxpY2U6cHc="}])
def test_missing_credentials_get_a_plain_bearer_challenge(
    client: TestClient, headers: dict[str, str]
) -> None:
    response = client.get("/whoami", headers=headers)
    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.headers["www-authenticate"] == "Bearer"
    body = response.json()
    assert body["type"] == "https://wallpaperhub.dev/problems/unauthorized"
    assert body["status"] == 401
    assert body["instance"] == "/whoami"


@pytest.mark.parametrize(
    "token",
    [
        "garbage",
        make_token(exp=int(time.time()) - 600),
        make_token(aud="media-svc"),
        make_token(typ="Refresh"),
    ],
    ids=["garbage", "expired", "wrong-audience", "refresh-token"],
)
def test_bad_tokens_get_401_with_invalid_token_challenge(client: TestClient, token: str) -> None:
    response = client.get("/whoami", headers=bearer(token))
    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'
    # one generic message for every failure: the client learns nothing about the check
    assert response.json()["detail"] == "The access token is invalid or has expired."


def test_identity_provider_outage_is_503_not_401(client: TestClient, keys: Keys) -> None:
    keys.down = True
    response = client.get("/whoami", headers=bearer(make_token()))
    assert response.status_code == 503
    assert response.headers["content-type"].startswith(PROBLEM)
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/service-unavailable"
    assert "www-authenticate" not in response.headers
