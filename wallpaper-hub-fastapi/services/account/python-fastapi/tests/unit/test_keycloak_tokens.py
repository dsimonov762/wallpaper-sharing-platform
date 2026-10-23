"""KeycloakTokenClient against a fake Keycloak token endpoint (httpx2 MockTransport)."""

import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs

import httpx2
import jwt
import pytest
from pydantic import SecretStr

from account.domain.exceptions import ServiceUnavailableException, UnauthorizedException
from account.infra.keycloak_tokens import KeycloakTokenClient

pytestmark = pytest.mark.asyncio

ISSUER = "http://kc/realms/wallpaperhub"
ENDPOINT = "/realms/wallpaperhub/protocol/openid-connect"


def refresh_token(**overrides: Any) -> SecretStr:
    claims = {"typ": "Refresh", "azp": "web-spa", "iss": ISSUER, "exp": int(time.time()) + 1800}
    return SecretStr(jwt.encode({**claims, **overrides}, "k" * 64, algorithm="HS512"))


class FakeTokenEndpoint:
    def __init__(self) -> None:
        self.requests: list[tuple[str, dict[str, str]]] = []
        self.answers: dict[str, httpx2.Response | Exception] = {}

    def answer(self, endpoint: str, outcome: httpx2.Response | Exception) -> None:
        self.answers[endpoint] = outcome

    def handle(self, request: httpx2.Request) -> httpx2.Response:
        form = {key: values[0] for key, values in parse_qs(request.content.decode()).items()}
        self.requests.append((request.url.path, form))
        outcome = self.answers.get(request.url.path.removeprefix(ENDPOINT))
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is not None:
            return outcome
        if request.url.path.endswith("/token"):
            return httpx2.Response(
                200,
                json={
                    "access_token": "new-access",
                    "refresh_token": "new-refresh",
                    "token_type": "Bearer",
                    "expires_in": 299,
                    "refresh_expires_in": 1799,
                    "scope": "profile email",
                },
            )
        return httpx2.Response(204)


@pytest.fixture
def endpoint() -> FakeTokenEndpoint:
    return FakeTokenEndpoint()


@pytest.fixture
def tokens(endpoint: FakeTokenEndpoint) -> KeycloakTokenClient:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(endpoint.handle))
    return KeycloakTokenClient(client, base_url="http://kc", realm="wallpaperhub", issuer=ISSUER)


def oauth_error(status: int, error: str = "invalid_grant") -> httpx2.Response:
    return httpx2.Response(status, json={"error": error, "error_description": "secret detail"})


# --- refresh ----------------------------------------------------------------------------------


async def test_refresh_exchanges_the_token_for_a_new_set(
    tokens: KeycloakTokenClient, endpoint: FakeTokenEndpoint
) -> None:
    token = refresh_token(azp="dev-tools")

    result = await tokens.refresh(token)

    assert (result.access_token, result.refresh_token) == ("new-access", "new-refresh")
    assert (result.token_type, result.expires_in, result.refresh_expires_in) == (
        "Bearer",
        299,
        1799,
    )
    path, form = endpoint.requests[0]
    assert path == f"{ENDPOINT}/token"
    assert form == {
        "grant_type": "refresh_token",
        "client_id": "dev-tools",  # taken from the token's azp claim
        "refresh_token": token.get_secret_value(),
    }
    assert "client_secret" not in form  # a public client: the refresh token is the credential


@pytest.mark.parametrize("status", [400, 401])
async def test_a_token_keycloak_rejects_is_a_401(
    tokens: KeycloakTokenClient, endpoint: FakeTokenEndpoint, status: int
) -> None:
    endpoint.answer("/token", oauth_error(status))

    with pytest.raises(UnauthorizedException):
        await tokens.refresh(refresh_token())


@pytest.mark.parametrize(
    "outcome", [500, 503, httpx2.ConnectError("boom"), httpx2.ReadTimeout("slow")]
)
async def test_keycloak_problems_are_service_unavailable(
    tokens: KeycloakTokenClient, endpoint: FakeTokenEndpoint, outcome: int | Exception
) -> None:
    endpoint.answer("/token", httpx2.Response(outcome) if isinstance(outcome, int) else outcome)

    with pytest.raises(ServiceUnavailableException):
        await tokens.refresh(refresh_token())


@pytest.mark.parametrize(
    "body", [{}, {"access_token": "a"}, {"access_token": "a", "refresh_token": "r"}, []]
)
async def test_an_unusable_answer_is_service_unavailable(
    tokens: KeycloakTokenClient, endpoint: FakeTokenEndpoint, body: Any
) -> None:
    endpoint.answer("/token", httpx2.Response(200, json=body))

    with pytest.raises(ServiceUnavailableException):
        await tokens.refresh(refresh_token())


@pytest.mark.parametrize(
    "token",
    [SecretStr("garbage"), refresh_token(typ="Bearer"), refresh_token(exp=1)],
    ids=["garbage", "access-token", "expired"],
)
async def test_a_token_that_fails_the_inspection_never_reaches_keycloak(
    tokens: KeycloakTokenClient, endpoint: FakeTokenEndpoint, token: SecretStr
) -> None:
    with pytest.raises(UnauthorizedException):
        await tokens.refresh(token)
    with pytest.raises(UnauthorizedException):
        await tokens.logout(token)

    assert endpoint.requests == []


# --- logout -----------------------------------------------------------------------------------


async def test_logout_sends_the_token_and_its_client(
    tokens: KeycloakTokenClient, endpoint: FakeTokenEndpoint
) -> None:
    token = refresh_token()

    await tokens.logout(token)

    path, form = endpoint.requests[0]
    assert path == f"{ENDPOINT}/logout"
    assert form == {"client_id": "web-spa", "refresh_token": token.get_secret_value()}


@pytest.mark.parametrize("status", [400, 401])
async def test_logout_with_a_rejected_token_is_a_401(
    tokens: KeycloakTokenClient, endpoint: FakeTokenEndpoint, status: int
) -> None:
    endpoint.answer("/logout", oauth_error(status))

    with pytest.raises(UnauthorizedException):
        await tokens.logout(refresh_token())


@pytest.mark.parametrize("outcome", [500, httpx2.ConnectError("boom")])
async def test_logout_problems_are_service_unavailable(
    tokens: KeycloakTokenClient, endpoint: FakeTokenEndpoint, outcome: int | Exception
) -> None:
    endpoint.answer("/logout", httpx2.Response(outcome) if isinstance(outcome, int) else outcome)

    with pytest.raises(ServiceUnavailableException):
        await tokens.logout(refresh_token())


# --- secrets stay secret ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "outcome", [oauth_error(400), httpx2.Response(500), httpx2.ConnectError("x")]
)
@pytest.mark.parametrize("action", ["refresh", "logout"])
async def test_the_refresh_token_never_reaches_logs_or_error_messages(
    tokens: KeycloakTokenClient,
    endpoint: FakeTokenEndpoint,
    caplog: pytest.LogCaptureFixture,
    action: str,
    outcome: httpx2.Response | Exception,
) -> None:
    endpoint.answer("/token" if action == "refresh" else "/logout", outcome)
    token = refresh_token()
    call: Callable[[SecretStr], Any] = getattr(tokens, action)

    with caplog.at_level(logging.DEBUG), pytest.raises(Exception) as info:  # noqa: PT011
        await call(token)

    assert token.get_secret_value() not in caplog.text
    assert token.get_secret_value() not in str(info.value)
    assert "secret detail" not in str(info.value)  # Keycloak's own wording stays in our logs
