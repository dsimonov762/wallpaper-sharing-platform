"""The users API against the real database (needs `just infra-up` + `just account-migrate`).

Tokens come from a fake identity provider (our own RSA key + fake key set), swapped into the
running app, so these tests need the database but not Keycloak. Step 3.8 adds tests with
real Keycloak tokens.
"""

import asyncio
import json
import time
from collections.abc import Mapping
from typing import Any, cast
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from account.security.jwks import JwksCache
from account.security.jwt_validator import TokenValidator

pytestmark = pytest.mark.integration

PASSWORD = "correct-horse-battery"

# --- fake identity provider ---------------------------------------------------------------

ISSUER = "http://localhost:8180/realms/wallpaperhub"
AUDIENCE = "account-svc"
KID = "integration-test-key"
_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


async def _fake_jwks() -> Mapping[str, object]:
    await asyncio.sleep(0)
    jwk = json.loads(RSAAlgorithm.to_jwk(_private_key.public_key()))
    jwk.update({"kid": KID, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def bearer(*roles: str, sub: str | None = None) -> dict[str, str]:
    """Authorization header for a valid token. `sub` is the caller's user id."""
    claims: dict[str, Any] = {
        "sub": sub or str(uuid4()),
        "iss": ISSUER,
        "aud": AUDIENCE,
        "typ": "Bearer",
        "exp": int(time.time()) + 300,
        "realm_access": {"roles": list(roles)},
    }
    token = jwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": KID})
    return {"Authorization": f"Bearer {token}"}


def admin() -> dict[str, str]:
    return bearer("USER", "ADMIN")


@pytest.fixture(autouse=True)
def trust_fake_identity_provider(client: TestClient) -> None:
    """Make the running app accept tokens signed by this file's key instead of Keycloak's."""
    app = cast(FastAPI, client.app)
    app.state.token_validator = TokenValidator(
        JwksCache(_fake_jwks), issuer=ISSUER, audience=AUDIENCE
    )


# --- helpers -----------------------------------------------------------------------------


def new_registration(**overrides: str) -> dict[str, str]:
    username = f"it_{uuid4().hex[:8]}"
    payload = {"username": username, "email": f"{username}@example.com", "password": PASSWORD}
    return {**payload, **overrides}


def register(client: TestClient, **overrides: str) -> dict[str, Any]:
    response = client.post("/api/v1/registrations", json=new_registration(**overrides))
    assert response.status_code == 201
    return response.json()


# --- registration stays public -------------------------------------------------------------


def test_register_returns_201_with_location_and_no_password(client: TestClient) -> None:
    payload = new_registration(displayName="Alice Example", locale="de")

    response = client.post("/api/v1/registrations", json=payload)  # no token on purpose

    body = response.json()
    assert response.status_code == 201
    assert response.headers["location"] == f"/api/v1/users/{body['id']}"
    assert body["username"] == payload["username"]
    assert body["displayName"] == "Alice Example"
    assert body["locale"] == "de"
    assert body["status"] == "ACTIVE"
    assert body["version"] == 1
    assert PASSWORD not in response.text
    assert "password" not in body


def test_display_name_defaults_to_username(client: TestClient) -> None:
    payload = new_registration()

    body = client.post("/api/v1/registrations", json=payload).json()

    assert body["displayName"] == payload["username"]


def test_duplicate_username_and_email_are_both_reported(client: TestClient) -> None:
    payload = new_registration()
    assert client.post("/api/v1/registrations", json=payload).status_code == 201

    response = client.post("/api/v1/registrations", json=payload)

    assert response.status_code == 409
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields == {"username", "email"}


def test_email_is_case_insensitive_for_duplicates(client: TestClient) -> None:
    first = new_registration()
    client.post("/api/v1/registrations", json=first)
    second = new_registration(email=first["email"].upper())

    response = client.post("/api/v1/registrations", json=second)

    assert response.status_code == 409
    assert [error["field"] for error in response.json()["errors"]] == ["email"]


# --- reading one user (any signed-in caller) -------------------------------------------------


def test_public_profile_hides_email(client: TestClient) -> None:
    created = register(client)

    response = client.get(f"/api/v1/users/{created['id']}", headers=bearer("USER"))

    assert response.status_code == 200
    assert response.json()["username"] == created["username"]
    assert "email" not in response.json()


def test_unknown_user_is_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/users/{uuid4()}", headers=bearer("USER"))

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


def test_reading_a_user_needs_a_token(client: TestClient) -> None:
    created = register(client)

    response = client.get(f"/api/v1/users/{created['id']}")

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["www-authenticate"] == "Bearer"


def test_a_garbage_token_is_401_with_invalid_token_challenge(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/users/{uuid4()}", headers={"Authorization": "Bearer not.a.token"}
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Bearer error="invalid_token"'


# --- deleting (owner or ADMIN) -------------------------------------------------------------


def test_owner_deletes_own_account_softly(client: TestClient) -> None:
    created = register(client)
    owner = bearer("USER", sub=created["id"])

    assert client.delete(f"/api/v1/users/{created['id']}", headers=owner).status_code == 204
    assert client.get(f"/api/v1/users/{created['id']}", headers=owner).status_code == 404
    assert client.delete(f"/api/v1/users/{created['id']}", headers=owner).status_code == 404


def test_admin_can_delete_anyone(client: TestClient) -> None:
    created = register(client)

    assert client.delete(f"/api/v1/users/{created['id']}", headers=admin()).status_code == 204
    assert client.get(f"/api/v1/users/{created['id']}", headers=admin()).status_code == 404


def test_stranger_cannot_delete_someone_else(client: TestClient) -> None:
    created = register(client)

    response = client.delete(f"/api/v1/users/{created['id']}", headers=bearer("USER"))

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert client.get(f"/api/v1/users/{created['id']}", headers=admin()).status_code == 200


def test_deleting_needs_a_token(client: TestClient) -> None:
    created = register(client)

    assert client.delete(f"/api/v1/users/{created['id']}").status_code == 401
    assert client.get(f"/api/v1/users/{created['id']}", headers=admin()).status_code == 200


def test_stranger_gets_403_even_for_ids_that_do_not_exist(client: TestClient) -> None:
    missing = f"/api/v1/users/{uuid4()}"

    assert client.delete(missing, headers=bearer("USER")).status_code == 403  # no id probing
    assert client.delete(missing, headers=admin()).status_code == 404


def test_deleted_username_stays_reserved(client: TestClient) -> None:
    payload = new_registration()
    created = client.post("/api/v1/registrations", json=payload).json()
    client.delete(f"/api/v1/users/{created['id']}", headers=admin())

    response = client.post("/api/v1/registrations", json=payload)

    assert response.status_code == 409


# --- listing (ADMIN only) ------------------------------------------------------------------


def test_listing_needs_a_token(client: TestClient) -> None:
    assert client.get("/api/v1/users").status_code == 401


@pytest.mark.parametrize("roles", [(), ("USER",), ("USER", "MODERATOR"), ("internal",)])
def test_listing_is_forbidden_without_admin_role(
    client: TestClient, roles: tuple[str, ...]
) -> None:
    response = client.get("/api/v1/users", headers=bearer(*roles))

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"


def test_authentication_is_checked_before_query_validation(client: TestClient) -> None:
    response = client.get("/api/v1/users", params={"size": 5000})  # invalid AND no token

    assert response.status_code == 401


def test_list_is_paged_sorted_and_excludes_deleted(client: TestClient) -> None:
    usernames = sorted(f"it_{uuid4().hex[:6]}{n}" for n in range(3))
    ids = {}
    for username in usernames:
        payload = new_registration(username=username, email=f"{username}@example.com")
        ids[username] = client.post("/api/v1/registrations", json=payload).json()["id"]
    client.delete(f"/api/v1/users/{ids[usernames[2]]}", headers=admin())

    response = client.get(
        "/api/v1/users",
        params={"page": 0, "size": 100, "sort": "username,asc"},
        headers=admin(),
    )

    body = response.json()
    assert response.status_code == 200
    assert body["size"] == 100
    assert body["totalPages"] >= 1
    listed = [item["username"] for item in body["items"] if item["username"] in usernames]
    assert listed == usernames[:2]  # sorted, and the deleted one is gone
    assert "email" in body["items"][0]  # list is the full (admin) view


def test_paging_envelope_adds_up(client: TestClient) -> None:
    for _ in range(3):
        register(client)

    page0 = client.get("/api/v1/users", params={"page": 0, "size": 2}, headers=admin()).json()
    page1 = client.get("/api/v1/users", params={"page": 1, "size": 2}, headers=admin()).json()

    assert len(page0["items"]) == 2
    assert page0["totalItems"] >= 3
    assert page0["totalPages"] == -(-page0["totalItems"] // 2)  # ceiling division
    assert {u["id"] for u in page0["items"]}.isdisjoint({u["id"] for u in page1["items"]})


def test_sorting_by_a_non_whitelisted_field_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/users", params={"sort": "email,asc"}, headers=admin())

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "sort"
