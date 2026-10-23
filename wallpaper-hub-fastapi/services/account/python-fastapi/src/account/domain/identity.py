"""The identity provider port: who creates the login account behind a user."""

from typing import Protocol
from uuid import UUID

from pydantic import SecretStr


class IdentityProvider(Protocol):
    """Manages the login identity behind a user (the user's id = Keycloak `sub`).

    Two implementations satisfy it: `LocalIdentityProvider` (development stand-in) and
    `KeycloakIdentityProvider` (the real admin-API client). Settings choose which one runs.
    """

    async def create_user(self, *, username: str, email: str, password: SecretStr) -> UUID:
        """Create the identity (enabled, with the USER role) and return its id."""
        ...

    async def delete_user(self, user_id: UUID) -> None:
        """Remove the identity. Used to undo `create_user` when registration fails later."""
        ...

    async def disable_user(self, user_id: UUID) -> None:
        """Block logins for the identity without deleting it (used when an account is deleted)."""
        ...
