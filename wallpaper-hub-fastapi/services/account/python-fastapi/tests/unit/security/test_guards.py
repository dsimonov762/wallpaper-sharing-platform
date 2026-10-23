"""Endpoint protection through a throw-away app: public / authenticated / restricted."""

from collections.abc import Callable, Iterator
from typing import Annotated, Any
from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from account.api.http.dependencies import CurrentUserDep
from account.api.http.guards import InternalDep, require_permission, require_role
from account.security.authorization import ensure_owner_or_permission
from account.security.current_user import CurrentUser
from account.security.permissions import Permission

MakeToken = Callable[..., dict[str, str]]  # the `auth_headers` fixture from conftest.py
ListUsers = Annotated[CurrentUser, Depends(require_permission(Permission.USER_LIST))]
ModeratorOrAdmin = Annotated[CurrentUser, Depends(require_role("MODERATOR", "ADMIN"))]


@pytest.fixture
def client(auth_app: FastAPI) -> Iterator[TestClient]:
    @auth_app.get("/public")
    async def public() -> dict[str, str]:
        return {"ok": "yes"}

    @auth_app.get("/authenticated")
    async def authenticated(user: CurrentUserDep) -> dict[str, str]:
        return {"id": user.id}

    @auth_app.get("/list")
    async def list_users(user: ListUsers) -> dict[str, str]:
        return {"id": user.id}

    @auth_app.get("/moderation")
    async def moderation(user: ModeratorOrAdmin) -> dict[str, str]:
        return {"id": user.id}

    @auth_app.get("/internal")
    async def internal(user: InternalDep) -> dict[str, str]:
        return {"id": user.id}

    @auth_app.delete("/users/{user_id}")
    async def delete_user(user_id: UUID, user: CurrentUserDep) -> dict[str, Any]:
        ensure_owner_or_permission(user, user_id, Permission.USER_DELETE)
        return {"deleted": str(user_id)}

    with TestClient(auth_app) as test_client:
        yield test_client


def test_public_endpoint_needs_no_token(client: TestClient) -> None:
    assert client.get("/public").status_code == 200


@pytest.mark.parametrize("path", ["/authenticated", "/list", "/moderation", "/internal"])
def test_protected_endpoints_answer_401_without_token(client: TestClient, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_any_valid_token_passes_the_authenticated_layer(
    client: TestClient, auth_headers: MakeToken
) -> None:
    assert client.get("/authenticated", headers=auth_headers()).status_code == 200  # no roles


@pytest.mark.parametrize(
    ("path", "roles", "expected"),
    [
        ("/list", ["USER"], 403),
        ("/list", ["MODERATOR"], 403),
        ("/list", ["ADMIN"], 200),
        ("/list", ["USER", "ADMIN"], 200),
        ("/moderation", ["USER"], 403),
        ("/moderation", ["MODERATOR"], 200),
        ("/moderation", ["ADMIN"], 200),
        ("/internal", ["USER", "MODERATOR", "ADMIN"], 403),  # even a full admin is not a service
        ("/internal", ["internal"], 200),
        ("/list", ["internal"], 403),
    ],
)
def test_role_and_permission_matrix(
    client: TestClient, auth_headers: MakeToken, path: str, roles: list[str], expected: int
) -> None:
    assert client.get(path, headers=auth_headers(*roles)).status_code == expected


def test_forbidden_is_problem_json_without_internals(
    client: TestClient, auth_headers: MakeToken
) -> None:
    response = client.get("/list", headers=auth_headers("USER"))
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["type"] == "https://wallpaperhub.dev/problems/forbidden"
    assert body["detail"] == "You do not have permission to perform this action."
    assert "USER_LIST" not in response.text
    assert "user:list" not in response.text  # never reveal which permission was missing


def test_owner_can_delete_self_but_not_others(client: TestClient, auth_headers: MakeToken) -> None:
    me = "0b0c9d3c-62a6-4c0e-9a77-3d2a4a0b1111"
    other = "7a1d4f52-9b1f-4d6a-8c55-1f3e2b9c2222"
    headers = auth_headers("USER", sub=me)
    assert client.delete(f"/users/{me}", headers=headers).status_code == 200
    assert client.delete(f"/users/{other}", headers=headers).status_code == 403


def test_admin_can_delete_anyone(client: TestClient, auth_headers: MakeToken) -> None:
    target = "7a1d4f52-9b1f-4d6a-8c55-1f3e2b9c2222"
    headers = auth_headers("ADMIN", sub="a-1")
    assert client.delete(f"/users/{target}", headers=headers).status_code == 200
