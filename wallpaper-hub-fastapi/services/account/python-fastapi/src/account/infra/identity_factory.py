"""Chooses the IdentityProvider from the settings."""

import httpx2

from account.config.settings import Settings
from account.domain.identity import IdentityProvider
from account.infra.keycloak_identity import KeycloakIdentityProvider
from account.infra.local_identity import LocalIdentityProvider


def create_identity_provider(settings: Settings, client: httpx2.AsyncClient) -> IdentityProvider:
    if settings.identity_provider == "local":
        return LocalIdentityProvider()
    secret = settings.keycloak_client_secret
    if secret is None:  # Settings already refuses this; the check keeps the types honest
        raise RuntimeError("keycloak_client_secret is required for the keycloak provider")
    return KeycloakIdentityProvider(
        client,
        base_url=settings.keycloak_base_url,
        realm=settings.keycloak_realm,
        client_id=settings.keycloak_client_id,
        client_secret=secret,
    )
