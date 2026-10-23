"""The real identity provider: Keycloak's admin REST API.

How it works, in short:

1. We sign in as OURSELVES: the `account-svc` client uses its secret to get an access token
   (OAuth2 "client credentials"). That token is cached and renewed shortly before it expires.
2. With that token we call the admin API: create a user, give them the USER role, and, when
   something goes wrong later, delete or disable them.

The account-svc service account needs exactly two roles of the `realm-management` client:
`manage-users` (create, delete, disable, assign roles) and `view-realm` (look up a role by
name). Anything broader would be more power than this service needs.

Failures are translated into the application's own exceptions, and the user's password is
never logged or put into an exception message.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from http import HTTPStatus
from typing import Any
from uuid import UUID

import httpx2
from pydantic import SecretStr

from account.domain.exceptions import (
    ConflictException,
    FieldIssue,
    ServiceUnavailableException,
    ValidationException,
)

logger = logging.getLogger(__name__)

USER_ROLE = "USER"
_TOKEN_SAFETY_MARGIN_S = 30.0  # renew this long before the token really expires


class KeycloakIdentityProvider:
    def __init__(
        self,
        client: httpx2.AsyncClient,
        *,
        base_url: str,
        realm: str,
        client_id: str,
        client_secret: SecretStr,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        base = base_url.rstrip("/")
        self._client = client  # owned by the app lifespan (created and closed there)
        self._token_url = f"{base}/realms/{realm}/protocol/openid-connect/token"
        self._admin_url = f"{base}/admin/realms/{realm}"
        self._client_id = client_id
        self._client_secret = client_secret
        self._clock = clock
        self._token: str | None = None
        self._token_expires_at = 0.0
        self._token_lock = asyncio.Lock()
        self._roles: dict[
            str, dict[str, Any]
        ] = {}  # role name -> representation (id never changes)

    # --- the IdentityProvider port ---------------------------------------------------------

    async def create_user(self, *, username: str, email: str, password: SecretStr) -> UUID:
        body = {
            "username": username,
            "email": email,
            "enabled": True,
            "emailVerified": True,  # no e-mail verification flow in this project yet
            "credentials": [
                {"type": "password", "value": password.get_secret_value(), "temporary": False}
            ],
        }
        response = await self._admin("POST", "/users", json=body)
        if response.status_code == HTTPStatus.CONFLICT:
            raise _conflict_from(response)
        if response.status_code == HTTPStatus.BAD_REQUEST:
            logger.warning("Keycloak rejected a new user: %s", _error_message(response))
            raise ValidationException("The identity provider rejected the registration data.")
        if response.status_code != HTTPStatus.CREATED:
            raise _unavailable(f"create user answered {response.status_code}")

        user_id = _id_from_location(response)
        try:
            await self._assign_role(user_id, USER_ROLE)
        except Exception:
            # The caller never learns this id, so nobody else could clean the user up.
            await self._delete_quietly(user_id)
            raise
        return user_id

    async def delete_user(self, user_id: UUID) -> None:
        response = await self._admin("DELETE", f"/users/{user_id}")
        if response.status_code not in (HTTPStatus.NO_CONTENT, HTTPStatus.NOT_FOUND):
            raise _unavailable(f"delete user answered {response.status_code}")

    async def disable_user(self, user_id: UUID) -> None:
        response = await self._admin("PUT", f"/users/{user_id}", json={"enabled": False})
        if response.status_code not in (HTTPStatus.NO_CONTENT, HTTPStatus.NOT_FOUND):
            raise _unavailable(f"disable user answered {response.status_code}")

    # --- helpers ---------------------------------------------------------------------------

    async def _assign_role(self, user_id: UUID, role_name: str) -> None:
        role = await self._role(role_name)
        response = await self._admin("POST", f"/users/{user_id}/role-mappings/realm", json=[role])
        if response.status_code != HTTPStatus.NO_CONTENT:
            raise _unavailable(f"assign role answered {response.status_code}")

    async def _role(self, name: str) -> dict[str, Any]:
        if name not in self._roles:
            response = await self._admin("GET", f"/roles/{name}")
            if response.status_code != HTTPStatus.OK:
                raise _unavailable(f"role {name} lookup answered {response.status_code}")
            self._roles[name] = response.json()
        return self._roles[name]

    async def _delete_quietly(self, user_id: UUID) -> None:
        try:
            await self.delete_user(user_id)
        except Exception:
            logger.error(
                "Could not remove Keycloak user %s after a failed setup; delete it by hand",
                user_id,
                exc_info=True,
            )

    async def _admin(self, method: str, path: str, *, json: Any = None) -> httpx2.Response:
        """Call the admin API. A 401 means our token went stale, so renew it and try once more."""
        response = await self._send(method, path, json, await self._access_token())
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            response = await self._send(
                method, path, json, await self._access_token(force_renew=True)
            )
        return response

    async def _send(self, method: str, path: str, json: Any, token: str) -> httpx2.Response:
        try:
            return await self._client.request(
                method,
                f"{self._admin_url}{path}",
                json=json,
                headers={"Authorization": f"Bearer {token}"},
            )
        except httpx2.HTTPError as error:
            raise _unavailable(f"{method} {path} failed: {type(error).__name__}") from error

    async def _access_token(self, *, force_renew: bool = False) -> str:
        async with self._token_lock:
            if force_renew or self._token is None or self._clock() >= self._token_expires_at:
                self._token = await self._fetch_token()
            return self._token

    async def _fetch_token(self) -> str:
        try:
            response = await self._client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret.get_secret_value(),
                },
            )
        except httpx2.HTTPError as error:
            raise _unavailable(f"token request failed: {type(error).__name__}") from error
        if response.status_code != HTTPStatus.OK:
            raise _unavailable(f"token request answered {response.status_code}")
        payload = response.json()
        lifetime = float(payload.get("expires_in", 60))
        self._token_expires_at = self._clock() + max(lifetime - _TOKEN_SAFETY_MARGIN_S, 0.0)
        return str(payload["access_token"])


def _unavailable(reason: str) -> ServiceUnavailableException:
    logger.error("Keycloak admin API problem: %s", reason)
    return ServiceUnavailableException("The identity provider is temporarily unavailable.")


def _error_message(response: httpx2.Response) -> str:
    try:
        message = response.json().get("errorMessage")
    except ValueError:
        return ""
    return message if isinstance(message, str) else ""


def _conflict_from(response: httpx2.Response) -> ConflictException:
    message = _error_message(response).lower()
    issues: list[FieldIssue] = []
    if "username" in message:
        issues.append(FieldIssue("username", "AlreadyExists", "This username is already taken."))
    if "email" in message:
        issues.append(
            FieldIssue("email", "AlreadyExists", "This email address is already registered.")
        )
    return ConflictException("The user already exists.", issues)


def _id_from_location(response: httpx2.Response) -> UUID:
    """Keycloak answers 201 with `Location: .../users/<new id>`."""
    location = response.headers.get("location", "")
    try:
        return UUID(location.rstrip("/").rsplit("/", 1)[-1])
    except ValueError as error:
        raise _unavailable("create user returned no usable Location header") from error
