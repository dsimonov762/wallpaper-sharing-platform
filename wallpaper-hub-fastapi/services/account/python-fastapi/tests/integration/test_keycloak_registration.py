"""Registration against a REAL Keycloak (needs `just infra-up`, the database and the realm from
realm-export.json). Skipped automatically when Keycloak is not running.

This is the proof of the whole chain: a user registered through our API can log in at Keycloak,
and the token Keycloak issues is accepted by our API for THAT user (token `sub` = `users.id`).
"""

import base64
import json
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from account.config.settings import get_settings
from account.main import create_app
from account.repository.models import UserEntity
from account.repository.user_repository import UserRepository

pytestmark = pytest.mark.integration

KEYCLOAK = "http://127.0.0.1:8180"
REALM = "wallpaperhub"
SERVICE_SECRET = "dev-secret-account-svc"  # from realm-export.json (local development only)
PASSWORD = "correct-horse-battery"


def _service_token() -> str:
    response = httpx2.post(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "account-svc",
            "client_secret": SERVICE_SECRET,
        },
        timeout=5.0,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _claims(token: str) -> dict[str, Any]:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))


def _find_users(prefix: str) -> list[dict[str, Any]]:
    response = httpx2.get(
        f"{KEYCLOAK}/admin/realms/{REALM}/users",
        params={"username": prefix, "max": 200},
        headers={"Authorization": f"Bearer {_service_token()}"},
        timeout=5.0,
    )
    response.raise_for_status()
    return [user for user in response.json() if user["username"].startswith(prefix)]


def _log_in(username: str, password: str = PASSWORD) -> httpx2.Response:
    return httpx2.post(
        f"{KEYCLOAK}/realms/{REALM}/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "dev-tools",
            "username": username,
            "password": password,
        },
        timeout=5.0,
    )


@pytest.fixture(scope="module", autouse=True)
def keycloak_is_ready() -> None:
    try:
        httpx2.get(f"{KEYCLOAK}/realms/{REALM}/.well-known/openid-configuration", timeout=2.0)
    except httpx2.HTTPError:
        pytest.skip("Keycloak is not running on localhost:8180 (just infra-up)")
    roles = _claims(_service_token()).get("resource_access", {}).get("realm-management", {})
    if "manage-users" not in roles.get("roles", []):
        pytest.fail(
            "The account-svc service account cannot manage users. Recreate Keycloak so the "
            "updated realm-export.json is imported (see the step 3.6 notes)."
        )


@pytest.fixture
def keycloak_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """The real app, configured to create real Keycloak users."""
    monkeypatch.setenv("ACCOUNT_IDENTITY_PROVIDER", "keycloak")
    monkeypatch.setenv("ACCOUNT_KEYCLOAK_CLIENT_SECRET", SERVICE_SECRET)
    get_settings.cache_clear()
    with TestClient(create_app()) as client:
        yield client
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _remove_test_users_from_keycloak() -> Iterator[None]:
    yield
    token = _service_token()
    for user in _find_users("it_"):
        httpx2.delete(
            f"{KEYCLOAK}/admin/realms/{REALM}/users/{user['id']}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )


def new_registration() -> dict[str, str]:
    username = f"it_{uuid4().hex[:8]}"
    return {"username": username, "email": f"{username}@example.com", "password": PASSWORD}


def test_a_registered_user_can_log_in_and_use_the_api_with_their_real_token(
    keycloak_client: TestClient,
) -> None:
    payload = new_registration()
    created = keycloak_client.post("/api/v1/registrations", json=payload)
    assert created.status_code == 201

    login = _log_in(payload["username"])
    assert login.status_code == 200
    token = login.json()["access_token"]
    claims = _claims(token)
    assert claims["sub"] == created.json()["id"]  # users.id == Keycloak sub
    assert "USER" in claims["realm_access"]["roles"]

    me = keycloak_client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["id"] == created.json()["id"]
    assert me.json()["email"] == payload["email"]

    edit = keycloak_client.patch(
        "/api/v1/users/me",
        json={"bio": "registered through Keycloak"},
        headers={"Authorization": f"Bearer {token}", "If-Match": me.headers["etag"]},
    )
    assert edit.status_code == 200


def test_a_username_already_taken_in_keycloak_is_a_clear_409(keycloak_client: TestClient) -> None:
    payload = new_registration()
    assert keycloak_client.post("/api/v1/registrations", json=payload).status_code == 201
    # Same username, different email: the database has no idea, only Keycloak knows.
    keycloak_only = {**payload, "email": f"other_{payload['email']}"}

    async def sees_nothing(self: UserRepository, username: str, email: str) -> set[str]:
        return set()

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(UserRepository, "username_or_email_taken", sees_nothing)
        response = keycloak_client.post("/api/v1/registrations", json=keycloak_only)

    assert response.status_code == 409
    assert [error["field"] for error in response.json()["errors"]] == ["username"]


def test_a_failed_database_step_leaves_no_keycloak_user_behind(
    keycloak_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = new_registration()

    async def broken_add(self: UserRepository, user: UserEntity) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(UserRepository, "add", broken_add)
    with pytest.raises(RuntimeError, match="database went away"):
        keycloak_client.post("/api/v1/registrations", json=payload)

    assert _find_users(payload["username"]) == []  # the compensating delete worked
    assert _log_in(payload["username"]).status_code != 200  # nobody can log in as that name


def test_deleting_the_account_blocks_the_login_but_keeps_the_identity(
    keycloak_client: TestClient,
) -> None:
    payload = new_registration()
    created = keycloak_client.post("/api/v1/registrations", json=payload).json()
    token = _log_in(payload["username"]).json()["access_token"]

    deleted = keycloak_client.delete(
        f"/api/v1/users/{created['id']}", headers={"Authorization": f"Bearer {token}"}
    )

    assert deleted.status_code == 204
    blocked = _log_in(payload["username"])
    assert blocked.status_code == 400
    assert blocked.json()["error_description"] == "Account disabled"
    (user,) = _find_users(payload["username"])
    assert user["enabled"] is False
    assert user["email"] == payload["email"]  # disabled, not wiped
