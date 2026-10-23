"""KeycloakIdentityProvider against a fake Keycloak (httpx2's MockTransport): no network."""

import json
import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID, uuid4

import httpx2
import pytest
from pydantic import SecretStr

from account.domain.exceptions import (
    ConflictException,
    ServiceUnavailableException,
    ValidationException,
)
from account.infra.keycloak_identity import KeycloakIdentityProvider

pytestmark = pytest.mark.asyncio

REALM = "wallpaperhub"
ADMIN = f"/admin/realms/{REALM}"
PASSWORD = SecretStr("a-long-password-123")


class FakeKeycloak:
    """Just enough of Keycloak's token endpoint and admin API to test our client."""

    def __init__(self) -> None:
        self.users: dict[str, dict[str, object]] = {}
        self.roles_of: dict[str, list[str]] = {}
        self.token_requests = 0
        self.accepted_tokens: set[str] = set()
        self.token_lifetime = 300
        self.secret = "secret"
        self.calls: list[tuple[str, str]] = []
        self.overrides: dict[tuple[str, str], int | Exception] = {}

    def fail(self, method: str, path_suffix: str, outcome: int | Exception) -> None:
        self.overrides[(method, path_suffix)] = outcome

    def revoke_tokens(self) -> None:
        self.accepted_tokens.clear()

    def transport(self) -> httpx2.MockTransport:
        return httpx2.MockTransport(self._handle)

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        for (method, suffix), outcome in self.overrides.items():
            if request.method == method and path.endswith(suffix):
                if isinstance(outcome, Exception):
                    raise outcome
                return httpx2.Response(outcome, json={"errorMessage": "forced"})

        if path.endswith("/protocol/openid-connect/token"):
            form = parse_qs(request.content.decode())
            if form["client_secret"] != [self.secret] or form["grant_type"] != [
                "client_credentials"
            ]:
                return httpx2.Response(401, json={"error": "unauthorized_client"})
            self.token_requests += 1
            token = f"token-{self.token_requests}"
            self.accepted_tokens.add(token)
            return httpx2.Response(
                200, json={"access_token": token, "expires_in": self.token_lifetime}
            )

        if (
            request.headers.get("authorization", "").removeprefix("Bearer ")
            not in self.accepted_tokens
        ):
            return httpx2.Response(401)
        return self._admin(request, path.removeprefix(ADMIN))

    def _admin(self, request: httpx2.Request, path: str) -> httpx2.Response:
        body: Any = json.loads(request.content) if request.content else None
        if request.method == "POST" and path == "/users":
            for existing in self.users.values():
                if existing["username"] == body["username"]:
                    return httpx2.Response(
                        409, json={"errorMessage": "User exists with same username"}
                    )
                if existing["email"] == body["email"]:
                    return httpx2.Response(
                        409, json={"errorMessage": "User exists with same email"}
                    )
            user_id = str(uuid4())
            self.users[user_id] = body
            self.roles_of[user_id] = []
            return httpx2.Response(201, headers={"Location": f"http://kc{ADMIN}/users/{user_id}"})
        if request.method == "GET" and path == "/roles/USER":
            return httpx2.Response(200, json={"id": "role-id-1", "name": "USER"})
        if path.startswith("/users/"):
            user_id = path.split("/")[2]
            if user_id not in self.users:
                return httpx2.Response(404)
            if request.method == "POST" and path.endswith("/role-mappings/realm"):
                self.roles_of[user_id] += [role["name"] for role in body]
                return httpx2.Response(204)
            if request.method == "DELETE":
                del self.users[user_id]
                return httpx2.Response(204)
            if request.method == "PUT":
                self.users[user_id]["enabled"] = body["enabled"]
                return httpx2.Response(204)
        return httpx2.Response(404)


class Clock:
    now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def keycloak() -> FakeKeycloak:
    return FakeKeycloak()


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def make_provider(keycloak: FakeKeycloak, clock: Clock) -> Callable[..., KeycloakIdentityProvider]:
    def make(*, wrong_secret: bool = False) -> KeycloakIdentityProvider:
        client = httpx2.AsyncClient(transport=keycloak.transport())
        return KeycloakIdentityProvider(
            client,
            base_url="http://kc",
            realm=REALM,
            client_id="account-svc",
            client_secret=SecretStr("wrong-secret" if wrong_secret else keycloak.secret),
            clock=clock,
        )

    return make


@pytest.fixture
def provider(make_provider: Callable[..., KeycloakIdentityProvider]) -> KeycloakIdentityProvider:
    return make_provider()


async def create(provider: KeycloakIdentityProvider, name: str = "alice") -> UUID:
    return await provider.create_user(username=name, email=f"{name}@example.com", password=PASSWORD)


# --- creating users ----------------------------------------------------------------------------


async def test_create_user_returns_keycloaks_id_and_sets_up_the_login(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    user_id = await create(provider)

    stored = keycloak.users[str(user_id)]
    assert stored["username"] == "alice"
    assert stored["enabled"] is True
    assert stored["emailVerified"] is True
    assert stored["credentials"] == [
        {"type": "password", "value": "a-long-password-123", "temporary": False}
    ]
    assert keycloak.roles_of[str(user_id)] == ["USER"]


async def test_duplicate_username_becomes_a_conflict_on_that_field(
    provider: KeycloakIdentityProvider,
) -> None:
    await create(provider)

    with pytest.raises(ConflictException) as info:
        await provider.create_user(username="alice", email="other@example.com", password=PASSWORD)

    assert [(i.field, i.code) for i in info.value.errors] == [("username", "AlreadyExists")]


async def test_duplicate_email_becomes_a_conflict_on_that_field(
    provider: KeycloakIdentityProvider,
) -> None:
    await create(provider)

    with pytest.raises(ConflictException) as info:
        await provider.create_user(username="bob", email="alice@example.com", password=PASSWORD)

    assert [(i.field, i.code) for i in info.value.errors] == [("email", "AlreadyExists")]


async def test_data_rejected_by_keycloak_is_a_400(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    keycloak.fail("POST", "/users", 400)

    with pytest.raises(ValidationException):
        await create(provider)


@pytest.mark.parametrize("outcome", [500, 503, 403, httpx2.ConnectError("boom")])
async def test_keycloak_problems_become_service_unavailable(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak, outcome: int | Exception
) -> None:
    keycloak.fail("POST", "/users", outcome)

    with pytest.raises(ServiceUnavailableException):
        await create(provider)


async def test_timeout_becomes_service_unavailable(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    keycloak.fail("POST", "/users", httpx2.ReadTimeout("slow"))

    with pytest.raises(ServiceUnavailableException):
        await create(provider)


# --- the half-created user must not be left behind ---------------------------------------------


@pytest.mark.parametrize("outcome", [500, 404, httpx2.ConnectError("boom")])
async def test_if_role_assignment_fails_the_new_user_is_removed(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak, outcome: int | Exception
) -> None:
    keycloak.fail("POST", "/role-mappings/realm", outcome)

    with pytest.raises(ServiceUnavailableException):
        await create(provider)

    assert keycloak.users == {}


async def test_if_the_role_does_not_exist_the_new_user_is_removed(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    keycloak.fail("GET", "/roles/USER", 404)

    with pytest.raises(ServiceUnavailableException):
        await create(provider)

    assert keycloak.users == {}


async def test_if_cleanup_also_fails_the_original_error_still_surfaces(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak, caplog: pytest.LogCaptureFixture
) -> None:
    keycloak.fail("POST", "/role-mappings/realm", 500)
    keycloak.fail("DELETE", "", 500)  # every DELETE fails

    with caplog.at_level(logging.ERROR), pytest.raises(ServiceUnavailableException):
        await create(provider)

    assert "delete it by hand" in caplog.text


# --- removing and disabling --------------------------------------------------------------------


async def test_delete_user_removes_it_and_tolerates_a_missing_one(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    user_id = await create(provider)

    await provider.delete_user(user_id)
    await provider.delete_user(user_id)  # already gone: fine

    assert keycloak.users == {}


async def test_delete_user_reports_real_failures(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    user_id = await create(provider)
    keycloak.fail("DELETE", f"/users/{user_id}", 500)

    with pytest.raises(ServiceUnavailableException):
        await provider.delete_user(user_id)


async def test_disable_user_blocks_logins_but_keeps_the_user(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    user_id = await create(provider)

    await provider.disable_user(user_id)
    await provider.disable_user(uuid4())  # unknown id: fine

    assert keycloak.users[str(user_id)]["enabled"] is False


# --- our own access token ----------------------------------------------------------------------


async def test_the_admin_token_is_fetched_once_and_reused(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    first = await create(provider, "one")
    await create(provider, "two")
    await provider.disable_user(first)

    assert keycloak.token_requests == 1


async def test_the_admin_token_is_renewed_shortly_before_it_expires(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak, clock: Clock
) -> None:
    await create(provider, "one")
    clock.now += 269  # 300s lifetime minus the 30s safety margin is still not reached
    await create(provider, "two")
    assert keycloak.token_requests == 1

    clock.now += 2
    await create(provider, "three")
    assert keycloak.token_requests == 2


async def test_a_rejected_token_is_renewed_and_the_call_retried_once(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    await create(provider, "one")
    keycloak.revoke_tokens()  # e.g. Keycloak restarted and forgot our token

    await create(provider, "two")  # must not fail

    assert keycloak.token_requests == 2
    assert len(keycloak.users) == 2


async def test_a_wrong_client_secret_is_service_unavailable_not_a_crash(
    make_provider: Callable[..., KeycloakIdentityProvider], caplog: pytest.LogCaptureFixture
) -> None:
    provider = make_provider(wrong_secret=True)

    with caplog.at_level(logging.ERROR), pytest.raises(ServiceUnavailableException):
        await create(provider)

    assert "wrong-secret" not in caplog.text


async def test_the_role_is_looked_up_once(
    provider: KeycloakIdentityProvider, keycloak: FakeKeycloak
) -> None:
    await create(provider, "one")
    await create(provider, "two")

    assert keycloak.calls.count(("GET", f"{ADMIN}/roles/USER")) == 1


# --- secrets stay secret -----------------------------------------------------------------------


@pytest.mark.parametrize("outcome", [400, 500, httpx2.ConnectError("boom")])
async def test_the_password_never_reaches_logs_or_error_messages(
    provider: KeycloakIdentityProvider,
    keycloak: FakeKeycloak,
    caplog: pytest.LogCaptureFixture,
    outcome: int | Exception,
) -> None:
    keycloak.fail("POST", "/users", outcome)

    with caplog.at_level(logging.DEBUG), pytest.raises(Exception) as info:  # noqa: PT011
        await create(provider)

    assert "a-long-password-123" not in caplog.text
    assert "a-long-password-123" not in str(info.value)
