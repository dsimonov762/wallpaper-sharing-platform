"""Access-token validation (README section 7, "Token validation").

Checks, in this order:

1. The header is readable and uses an algorithm we allow (never trust the token
   to choose: ``alg=none`` and HS256 "key confusion" attacks stop here).
2. The key id (``kid``) maps to a cached public key (see ``jwks.py``).
3. Signature, ``iss``, ``aud``, ``exp`` and ``nbf`` (with clock-skew leeway).
4. Required claims exist, and the ``typ`` claim is ``Bearer``
   (so a refresh or ID token cannot be used as an access token).

Failures raise ``TokenRejectedError`` with a short reason meant for logs.
"""

from typing import Any

import jwt

from account.security.errors import TokenRejectedError
from account.security.jwks import JwksCache

REQUIRED_CLAIMS = ("exp", "iss", "aud", "sub")


class TokenValidator:
    def __init__(
        self,
        jwks: JwksCache,
        *,
        issuer: str,
        audience: str,
        leeway_seconds: int = 30,
        algorithms: tuple[str, ...] = ("RS256",),
    ) -> None:
        self._jwks = jwks
        self._issuer = issuer
        self._audience = audience
        self._leeway = leeway_seconds
        self._algorithms = algorithms

    async def validate(self, token: str) -> dict[str, Any]:
        """Return the verified claims of ``token`` or raise ``TokenRejectedError``."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise TokenRejectedError("malformed") from exc

        if header.get("alg") not in self._algorithms:
            raise TokenRejectedError("bad_algorithm")
        kid = header.get("kid")
        if not isinstance(kid, str):
            raise TokenRejectedError("missing_kid")

        key = await self._jwks.get_key(kid)

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": list(REQUIRED_CLAIMS)},
            )
        except jwt.ExpiredSignatureError as exc:
            raise TokenRejectedError("expired") from exc
        except jwt.ImmatureSignatureError as exc:
            raise TokenRejectedError("not_yet_valid") from exc
        except jwt.InvalidAudienceError as exc:
            raise TokenRejectedError("bad_audience") from exc
        except jwt.InvalidIssuerError as exc:
            raise TokenRejectedError("bad_issuer") from exc
        except jwt.MissingRequiredClaimError as exc:
            raise TokenRejectedError("missing_claim") from exc
        except jwt.InvalidSignatureError as exc:
            raise TokenRejectedError("bad_signature") from exc
        except jwt.PyJWTError as exc:
            raise TokenRejectedError("malformed") from exc

        if claims.get("typ") != "Bearer":
            raise TokenRejectedError("bad_type")
        return claims
