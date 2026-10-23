"""A quick look at a refresh token before we forward it to Keycloak (README section 7).

IMPORTANT: this is an INSPECTION, not a validation. Keycloak signs refresh tokens with a
key that only Keycloak holds, so no other service can check the signature. We only read
the claims to turn obvious junk away early (not a JWT, an access token instead of a refresh
token, another realm's token, already expired) and to learn which client the token was issued
to. Keycloak then does the real check, and its answer is the only one that counts.

Nothing read here may be trusted for anything except choosing the `client_id` we send along:
anybody can write any claims into a token they made up.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt

from account.domain.exceptions import UnauthorizedException

logger = logging.getLogger(__name__)

INVALID_REFRESH_TOKEN = "The refresh token is invalid or has expired."  # noqa: S105  (a message)


@dataclass(frozen=True, slots=True)
class RefreshTokenInfo:
    client_id: str  # the `azp` claim: the client Keycloak issued this token to


def inspect_refresh_token(
    token: str, *, issuer: str, clock: Callable[[], float] = time.time
) -> RefreshTokenInfo:
    """Return who the token was issued to, or raise ``UnauthorizedException`` (401)."""
    try:
        claims: dict[str, Any] = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as error:
        raise _reject("not a readable JWT") from error

    if claims.get("typ") != "Refresh":
        raise _reject("typ is not Refresh")
    if claims.get("iss") != issuer:
        raise _reject("issued by another realm")
    client_id = claims.get("azp")
    if not isinstance(client_id, str) or not client_id:
        raise _reject("no azp claim")
    expires_at = claims.get("exp")
    if isinstance(expires_at, bool) or not isinstance(expires_at, int | float):
        raise _reject("no exp claim")
    if expires_at <= clock():
        raise _reject("expired")
    return RefreshTokenInfo(client_id=client_id)


def _reject(reason: str) -> UnauthorizedException:
    logger.info("Refresh token rejected before reaching Keycloak: %s", reason)  # never the token
    return UnauthorizedException(INVALID_REFRESH_TOKEN)
