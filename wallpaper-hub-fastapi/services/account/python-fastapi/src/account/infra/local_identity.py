"""Development stand-in for Keycloak's admin API."""

from uuid import UUID, uuid4

from pydantic import SecretStr


class LocalIdentityProvider:
    """Invents an id and discards the password. Used when ACCOUNT_IDENTITY_PROVIDER=local."""

    async def create_user(self, *, username: str, email: str, password: SecretStr) -> UUID:
        return uuid4()

    async def delete_user(self, user_id: UUID) -> None:
        """Nothing was ever created, so there is nothing to remove."""

    async def disable_user(self, user_id: UUID) -> None:
        """There is no real login to block."""
