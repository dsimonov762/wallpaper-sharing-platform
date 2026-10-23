"""Exchanges and revokes refresh tokens at Keycloak's token endpoints (README section 7).

Educational: normally a resource server never sees refresh tokens, because the client app
talks to Keycloak directly. Here account-service plays the go-between so the two OIDC calls
are visible in our own code:

* refresh: `grant_type=refresh_token` gives a new access token (and a new refresh token)
* logout:  ends the Keycloak session, which also kills every refresh token of that session

The client is a PUBLIC client (web-spa), so no client secret is sent: the refresh token itself
is the credential. It is never logged and never placed in an exception message.
"""

import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any

import httpx2
from pydantic import SecretStr

from account.domain.exceptions import ServiceUnavailableException, UnauthorizedException
from account.security.refresh_token import INVALID_REFRESH_TOKEN, inspect_refresh_token

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TokenSet:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    refresh_expires_in: int


class KeycloakTokenClient:
    def __init__(
        self, client: httpx2.AsyncClient, *, base_url: str, realm: str, issuer: str
    ) -> None:
        endpoint = f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect"
        self._client = client  # owned by the app lifespan
        self._token_url = f"{endpoint}/token"
        self._logout_url = f"{endpoint}/logout"
        self._issuer = issuer

    async def refresh(self, refresh_token: SecretStr) -> TokenSet:
        client_id = self._inspect(refresh_token)
        response = await self._post(
            self._token_url,
            {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token.get_secret_value(),
            },
        )
        _raise_for_rejection(response)
        if response.status_code != HTTPStatus.OK:
            raise _unavailable(f"token endpoint answered {response.status_code}")
        return _token_set_from(response)

    async def logout(self, refresh_token: SecretStr) -> None:
        """End the session. Keycloak answers 204 for a repeated logout, and so do we."""
        client_id = self._inspect(refresh_token)
        response = await self._post(
            self._logout_url,
            {"client_id": client_id, "refresh_token": refresh_token.get_secret_value()},
        )
        _raise_for_rejection(response)
        if response.status_code not in (HTTPStatus.NO_CONTENT, HTTPStatus.OK):
            raise _unavailable(f"logout endpoint answered {response.status_code}")

    def _inspect(self, refresh_token: SecretStr) -> str:
        return inspect_refresh_token(
            refresh_token.get_secret_value(), issuer=self._issuer
        ).client_id

    async def _post(self, url: str, form: dict[str, str]) -> httpx2.Response:
        try:
            return await self._client.post(url, data=form)
        except httpx2.HTTPError as error:
            raise _unavailable(f"request failed: {type(error).__name__}") from error


def _raise_for_rejection(response: httpx2.Response) -> None:
    """Keycloak says 400/401 + an OAuth error code when it does not accept the token or client."""
    if response.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.UNAUTHORIZED):
        logger.info("Keycloak rejected a refresh token: %s", _oauth_error(response))
        raise UnauthorizedException(INVALID_REFRESH_TOKEN)


def _oauth_error(response: httpx2.Response) -> str:
    try:
        error = response.json().get("error")
    except ValueError:
        return "unreadable answer"
    return error if isinstance(error, str) else "unknown"


def _token_set_from(response: httpx2.Response) -> TokenSet:
    try:
        payload: dict[str, Any] = response.json()
        return TokenSet(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload["refresh_token"]),
            token_type=str(payload.get("token_type", "Bearer")),
            expires_in=int(payload["expires_in"]),
            refresh_expires_in=int(payload.get("refresh_expires_in", 0)),
        )
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        raise _unavailable("token endpoint returned an unusable answer") from error


def _unavailable(reason: str) -> ServiceUnavailableException:
    logger.error("Keycloak token endpoint problem: %s", reason)
    return ServiceUnavailableException("Authentication is temporarily unavailable.")
