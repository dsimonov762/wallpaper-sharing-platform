"""Conversion from the Keycloak token result to the API response."""

from account.dto.auth import TokenResponse
from account.infra.keycloak_tokens import TokenSet


def to_token_response(tokens: TokenSet) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
        refresh_expires_in=tokens.refresh_expires_in,
    )
