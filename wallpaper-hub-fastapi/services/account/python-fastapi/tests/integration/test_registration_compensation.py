"""Registration touches two systems (identity provider + database). These tests prove that the
two never drift apart. Needs the database; a recording stand-in plays the identity provider."""

import logging
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from account.repository.models import UserEntity
from account.repository.user_repository import UserRepository

pytestmark = pytest.mark.integration

Login = Any  # the `auth_headers` fixture


class RecordingIdentity:
    """An IdentityProvider that remembers what it was asked and can be told to fail."""

    def __init__(self) -> None:
        self.created: list[UUID] = []
        self.deleted: list[UUID] = []
        self.disabled: list[UUID] = []
        self.fail_delete = False
        self.fail_disable = False

    async def create_user(self, *, username: str, email: str, password: SecretStr) -> UUID:
        user_id = uuid4()
        self.created.append(user_id)
        return user_id

    async def delete_user(self, user_id: UUID) -> None:
        if self.fail_delete:
            raise RuntimeError("identity provider is down")
        self.deleted.append(user_id)

    async def disable_user(self, user_id: UUID) -> None:
        if self.fail_disable:
            raise RuntimeError("identity provider is down")
        self.disabled.append(user_id)


@pytest.fixture
def identity(client: TestClient) -> RecordingIdentity:
    recording = RecordingIdentity()
    client.app.state.identity_provider = recording  # type: ignore[attr-defined]
    return recording


def registration() -> dict[str, str]:
    username = f"it_{uuid4().hex[:8]}"
    return {
        "username": username,
        "email": f"{username}@example.com",
        "password": "correct-horse-battery",
    }


def test_a_successful_registration_uses_the_identity_providers_id(
    client: TestClient, identity: RecordingIdentity
) -> None:
    response = client.post("/api/v1/registrations", json=registration())

    assert response.status_code == 201
    assert [UUID(response.json()["id"])] == identity.created  # users.id == identity id
    assert identity.deleted == []


def test_if_the_database_fails_the_identity_is_removed_again(
    client: TestClient, identity: RecordingIdentity, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken_add(self: UserRepository, user: UserEntity) -> None:
        raise RuntimeError("database went away")

    monkeypatch.setattr(UserRepository, "add", broken_add)

    with pytest.raises(RuntimeError, match="database went away"):
        client.post("/api/v1/registrations", json=registration())

    assert len(identity.created) == 1
    assert identity.deleted == identity.created  # no orphan login left behind


def test_a_lost_race_on_the_unique_constraint_is_a_409_and_also_cleans_up(
    client: TestClient, identity: RecordingIdentity, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = registration()
    assert client.post("/api/v1/registrations", json=payload).status_code == 201

    async def sees_nothing(self: UserRepository, username: str, email: str) -> set[str]:
        return set()  # as if both requests passed the "is it taken?" check at the same moment

    monkeypatch.setattr(UserRepository, "username_or_email_taken", sees_nothing)
    response = client.post("/api/v1/registrations", json=payload)

    assert response.status_code == 409
    fields = {error["field"] for error in response.json()["errors"]}
    assert fields
    assert fields <= {"username", "email"}  # Postgres reports the first constraint it hits
    assert len(identity.created) == 2
    assert identity.deleted == [identity.created[1]]  # only the second, failed attempt is undone


def test_if_the_cleanup_itself_fails_the_real_error_still_reaches_the_client(
    client: TestClient,
    identity: RecordingIdentity,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    payload = registration()
    client.post("/api/v1/registrations", json=payload)

    async def sees_nothing(self: UserRepository, username: str, email: str) -> set[str]:
        return set()

    monkeypatch.setattr(UserRepository, "username_or_email_taken", sees_nothing)
    identity.fail_delete = True
    with caplog.at_level(logging.ERROR):
        response = client.post("/api/v1/registrations", json=payload)

    assert response.status_code == 409  # not a 500 caused by the failed cleanup
    assert "delete it by hand" in caplog.text


def test_deleting_an_account_disables_its_login(
    client: TestClient, identity: RecordingIdentity, auth_headers: Login
) -> None:
    created = client.post("/api/v1/registrations", json=registration()).json()
    owner = auth_headers("USER", sub=created["id"])

    response = client.delete(f"/api/v1/users/{created['id']}", headers=owner)

    assert response.status_code == 204
    assert identity.disabled == [UUID(created["id"])]


def test_a_failure_to_disable_the_login_does_not_fail_the_delete(
    client: TestClient,
    identity: RecordingIdentity,
    auth_headers: Login,
    caplog: pytest.LogCaptureFixture,
) -> None:
    created = client.post("/api/v1/registrations", json=registration()).json()
    owner = auth_headers("USER", sub=created["id"])
    identity.fail_disable = True

    with caplog.at_level(logging.ERROR):
        response = client.delete(f"/api/v1/users/{created['id']}", headers=owner)

    assert response.status_code == 204
    assert client.get(f"/api/v1/users/{created['id']}", headers=owner).status_code == 404
    assert "Could not disable the login" in caplog.text
