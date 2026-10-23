"""Errors raised while checking an access token.

Two different failures need two different HTTP answers later (step 3.2):

* ``TokenRejectedError``  -> the caller's token is bad            -> 401
* ``JwksUnavailableError`` -> WE cannot fetch Keycloak's keys     -> 503

Mixing them up would tell a valid user "your token is wrong" just because
Keycloak is restarting.
"""

from typing import Literal

RejectReason = Literal[
    "malformed",
    "bad_algorithm",
    "missing_kid",
    "unknown_key",
    "bad_signature",
    "expired",
    "not_yet_valid",
    "bad_issuer",
    "bad_audience",
    "missing_claim",
    "bad_type",
]


class TokenError(Exception):
    """Base class for all token-related failures."""


class TokenRejectedError(TokenError):
    """The token is not acceptable. ``reason`` is for logs, never for the client."""

    def __init__(self, reason: RejectReason) -> None:
        super().__init__(reason)
        self.reason: RejectReason = reason


class JwksUnavailableError(TokenError):
    """The signing keys could not be loaded from the identity provider."""
