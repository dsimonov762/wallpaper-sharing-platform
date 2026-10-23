"""GET and PATCH /users/me with ETag and If-Match (needs `just infra-up` + `just account-migrate`).

The idea in one picture: GET hands out a label (ETag) for the version you looked at; PATCH must
hand it back (If-Match). If someone else saved in between, the labels differ and the edit is
refused (412) instead of silently erasing their change.
"""

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from account.domain.exceptions import PreconditionFailedException
from account.domain.user_service import UserService
from account.infra.local_identity import LocalIdentityProvider
from account.repository.database import create_session_factory
from account.repository.models import UserEntity
from account.repository.user_repository import UserRepository

pytestmark = pytest.mark.integration

Login = Callable[..., dict[str, str]]  # the `auth_headers` fixture
ME = "/api/v1/users/me"


def register(client: TestClient, **overrides: str) -> dict[str, Any]:
    username = f"it_{uuid4().hex[:8]}"
    payload = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "correct-horse-battery",
        **overrides,
    }
    response = client.post("/api/v1/registrations", json=payload)
    assert response.status_code == 201
    return response.json()


def patch(
    client: TestClient, headers: dict[str, str], body: dict[str, Any], if_match: str | None
) -> Any:
    extra = {} if if_match is None else {"If-Match": if_match}
    return client.patch(ME, json=body, headers={**headers, **extra})


# --- reading your own profile ----------------------------------------------------------------


def test_me_needs_a_token(client: TestClient) -> None:
    assert client.get(ME).status_code == 401
    assert client.patch(ME, json={"bio": "x"}).status_code == 401


def test_me_needs_the_profile_permissions(client: TestClient, auth_headers: Login) -> None:
    created = register(client)
    no_roles = auth_headers(sub=created["id"])
    service_account = auth_headers("internal", sub=created["id"])

    assert client.get(ME, headers=no_roles).status_code == 403
    assert client.get(ME, headers=service_account).status_code == 403
    assert patch(client, no_roles, {"bio": "x"}, '"1"').status_code == 403


def test_get_me_returns_the_full_profile_with_an_etag(
    client: TestClient, auth_headers: Login
) -> None:
    created = register(client, displayName="Alice Example", locale="de")

    response = client.get(ME, headers=auth_headers("USER", sub=created["id"]))

    body = response.json()
    assert response.status_code == 200
    assert body["id"] == created["id"]
    assert body["email"] == created["email"]  # the owner sees the full view
    assert body["displayName"] == "Alice Example"
    assert response.headers["etag"] == f'"{body["version"]}"'


def test_me_is_not_mistaken_for_a_user_id(client: TestClient, auth_headers: Login) -> None:
    created = register(client)

    response = client.get(ME, headers=auth_headers("USER", sub=created["id"]))

    assert response.status_code == 200  # a 400 here would mean "me" was parsed as a UUID


def test_get_me_without_a_profile_is_404(client: TestClient, auth_headers: Login) -> None:
    assert client.get(ME, headers=auth_headers("USER")).status_code == 404  # sub has no row
    assert client.get(ME, headers=auth_headers("USER", sub="not-a-uuid")).status_code == 404


# --- the If-Match rules ----------------------------------------------------------------------


def test_patch_without_if_match_is_428_and_changes_nothing(
    client: TestClient, auth_headers: Login
) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])

    response = patch(client, me, {"bio": "hello"}, if_match=None)

    assert response.status_code == 428
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/precondition-required"
    assert client.get(ME, headers=me).json()["bio"] is None


def test_patch_with_a_stale_etag_is_412_and_changes_nothing(
    client: TestClient, auth_headers: Login
) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])

    response = patch(client, me, {"bio": "hello"}, if_match='"999"')

    assert response.status_code == 412
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["type"] == "https://wallpaperhub.dev/problems/precondition-failed"
    assert client.get(ME, headers=me).json()["bio"] is None


def test_patch_with_the_current_etag_saves_and_returns_a_new_etag(
    client: TestClient, auth_headers: Login
) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    before = client.get(ME, headers=me)

    response = patch(client, me, {"bio": "Hello!"}, if_match=before.headers["etag"])

    body = response.json()
    assert response.status_code == 200
    assert body["bio"] == "Hello!"
    assert body["version"] == before.json()["version"] + 1
    assert body["updatedAt"] != before.json()["updatedAt"]
    assert response.headers["etag"] == f'"{body["version"]}"'
    assert response.headers["etag"] != before.headers["etag"]
    assert client.get(ME, headers=me).json()["bio"] == "Hello!"


def test_the_second_editor_with_an_old_etag_is_refused(
    client: TestClient, auth_headers: Login
) -> None:
    """Lost update: two tabs load the profile, both save. The second save must not win blindly."""
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    etag_both_saw = client.get(ME, headers=me).headers["etag"]

    first = patch(client, me, {"displayName": "First"}, etag_both_saw)
    second = patch(client, me, {"displayName": "Second"}, etag_both_saw)

    assert first.status_code == 200
    assert second.status_code == 412
    assert client.get(ME, headers=me).json()["displayName"] == "First"


def test_chained_edits_work_when_each_uses_the_etag_it_just_received(
    client: TestClient, auth_headers: Login
) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    etag = client.get(ME, headers=me).headers["etag"]

    for name in ("One", "Two", "Three"):
        response = patch(client, me, {"displayName": name}, etag)
        assert response.status_code == 200
        etag = response.headers["etag"]

    assert client.get(ME, headers=me).json()["displayName"] == "Three"


@pytest.mark.parametrize("if_match", ["*", '"999", "{current}"'])
def test_star_and_tag_lists_are_accepted(
    client: TestClient, auth_headers: Login, if_match: str
) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    current = client.get(ME, headers=me).headers["etag"].strip('"')

    response = patch(client, me, {"bio": "ok"}, if_match.format(current=current))

    assert response.status_code == 200


def test_a_weak_etag_never_matches(client: TestClient, auth_headers: Login) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    etag = client.get(ME, headers=me).headers["etag"]

    assert patch(client, me, {"bio": "x"}, f"W/{etag}").status_code == 412


@pytest.mark.parametrize("if_match", ["", "3", "garbage", '"1" "2"'])
def test_a_malformed_if_match_is_400(
    client: TestClient, auth_headers: Login, if_match: str
) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])

    response = patch(client, me, {"bio": "x"}, if_match)

    assert response.status_code == 400
    assert response.json()["errors"][0]["field"] == "If-Match"


# --- what a PATCH may change -----------------------------------------------------------------


def test_only_the_sent_fields_change(client: TestClient, auth_headers: Login) -> None:
    created = register(client, displayName="Alice", locale="de")
    me = auth_headers("USER", sub=created["id"])
    etag = client.get(ME, headers=me).headers["etag"]

    response = patch(client, me, {"bio": "Just a bio"}, etag)

    body = response.json()
    assert body["bio"] == "Just a bio"
    assert body["displayName"] == "Alice"  # untouched
    assert body["locale"] == "de"  # untouched


def test_a_field_you_do_not_send_is_not_cleared(client: TestClient, auth_headers: Login) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    saved = patch(client, me, {"bio": "Keep me"}, client.get(ME, headers=me).headers["etag"])

    response = patch(client, me, {"displayName": "Renamed"}, saved.headers["etag"])

    assert response.status_code == 200
    assert response.json()["displayName"] == "Renamed"
    assert response.json()["bio"] == "Keep me"  # omitted is not the same as null


def test_null_clears_the_bio(client: TestClient, auth_headers: Login) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    etag = patch(client, me, {"bio": "temporary"}, client.get(ME, headers=me).headers["etag"])

    response = patch(client, me, {"bio": None}, etag.headers["etag"])

    assert response.status_code == 200
    assert response.json()["bio"] is None


def test_an_empty_patch_changes_nothing_and_keeps_the_version(
    client: TestClient, auth_headers: Login
) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    before = client.get(ME, headers=me)

    response = patch(client, me, {}, before.headers["etag"])

    assert response.status_code == 200
    assert response.json()["version"] == before.json()["version"]
    assert response.headers["etag"] == before.headers["etag"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"displayName": None}, "displayName"),  # cannot be cleared
        ({"displayName": "   "}, "displayName"),
        ({"displayName": "x" * 101}, "displayName"),
        ({"bio": "x" * 501}, "bio"),
        ({"locale": "fr"}, "locale"),
        ({"locale": None}, "locale"),
        ({"email": "new@example.com"}, "email"),  # not editable here
        ({"status": "SUSPENDED"}, "status"),
        ({"version": 99}, "version"),
        ({"id": str(uuid4())}, "id"),
    ],
)
def test_invalid_or_forbidden_fields_are_400(
    client: TestClient, auth_headers: Login, body: dict[str, Any], field: str
) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    etag = client.get(ME, headers=me).headers["etag"]

    response = patch(client, me, body, etag)

    assert response.status_code == 400
    assert field in {error["field"] for error in response.json()["errors"]}
    after = client.get(ME, headers=me).json()
    assert after["email"] == created["email"]
    assert after["status"] == "ACTIVE"


def test_a_user_can_only_edit_their_own_profile(client: TestClient, auth_headers: Login) -> None:
    alice, bob = register(client), register(client)
    alice_headers = auth_headers("USER", sub=alice["id"])
    etag = client.get(ME, headers=alice_headers).headers["etag"]

    patch(client, alice_headers, {"displayName": "Alice Edited"}, etag)

    bob_view = client.get(ME, headers=auth_headers("USER", sub=bob["id"])).json()
    assert bob_view["displayName"] == bob["username"]  # default display name, unchanged
    public = client.get(f"/api/v1/users/{alice['id']}", headers=auth_headers("USER")).json()
    assert public["displayName"] == "Alice Edited"


def test_a_deleted_account_has_no_profile(client: TestClient, auth_headers: Login) -> None:
    created = register(client)
    me = auth_headers("USER", sub=created["id"])
    client.delete(f"/api/v1/users/{created['id']}", headers=me)

    assert client.get(ME, headers=me).status_code == 404
    assert patch(client, me, {"bio": "x"}, "*").status_code == 404


# --- the race the version check alone cannot catch ---------------------------------------------


class RacingRepository(UserRepository):
    """After reading the user, sneaks in another writer's save, like a second request would."""

    def __init__(self, session: Any, engine: AsyncEngine) -> None:
        super().__init__(session)
        self._engine = engine

    async def get(self, user_id: UUID) -> UserEntity | None:
        user = await super().get(user_id)
        async with self._engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE users SET display_name = 'someone else', version = version + 1 "
                    "WHERE id = :id"
                ),
                {"id": user_id},
            )
        return user


@pytest.mark.asyncio
async def test_a_save_between_read_and_commit_is_a_412_not_a_lost_update(
    client: TestClient, engine: AsyncEngine
) -> None:
    created = register(client)
    user_id = UUID(created["id"])

    async with create_session_factory(engine)() as session:
        service = UserService(session, RacingRepository(session, engine), LocalIdentityProvider())
        with pytest.raises(PreconditionFailedException):
            # The caller's ETag matches what we read (version 1), but the row changes
            # before our UPDATE runs. The version column makes that UPDATE touch no rows.
            await service.update_profile(user_id, {"display_name": "mine"}, frozenset({1}))

    async with create_session_factory(engine)() as session:
        stored = await session.get(UserEntity, user_id)
        assert stored is not None
        assert stored.display_name == "someone else"
        assert stored.version == 2
