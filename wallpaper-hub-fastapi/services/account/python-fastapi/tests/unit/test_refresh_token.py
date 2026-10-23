"""The quick look we take at a refresh token before forwarding it to Keycloak."""

import logging
import time
from typing import Any

import jwt
import pytest

from account.domain.exceptions import UnauthorizedException
from account.security.refresh_token import inspect_refresh_token

ISSUER = "http://localhost:8180/realms/wallpaperhub"
KEYCLOAK_LIKE_SECRET = "x" * 64  # Keycloak signs refresh tokens with HS512 and a key only it knows


def make_token(**overrides: Any) -> str:
    claims: dict[str, Any] = {
        "typ": "Refresh",
        "azp": "web-spa",
        "iss": ISSUER,
        "exp": int(time.time()) + 1800,
        **overrides,
    }
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, KEYCLOAK_LIKE_SECRET, algorithm="HS512")


def test_a_well_formed_refresh_token_reveals_its_client() -> None:
    info = inspect_refresh_token(make_token(azp="dev-tools"), issuer=ISSUER)

    assert info.client_id == "dev-tools"


def test_the_signature_is_deliberately_not_checked() -> None:
    """Only Keycloak can verify it. This is why the result is never trusted for anything else."""
    forged = jwt.encode(
        {"typ": "Refresh", "azp": "web-spa", "iss": ISSUER, "exp": 9_999_999_999},
        "some-key-nobody-knows-about-1234567890",
        algorithm="HS256",
    )

    assert inspect_refresh_token(forged, issuer=ISSUER).client_id == "web-spa"


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-jwt",
        "a.b.c",
        make_token(typ="Bearer"),  # an access token is not a refresh token
        make_token(typ="ID"),
        make_token(typ="Offline"),
        make_token(typ=None),
        make_token(iss="http://evil.example/realms/other"),
        make_token(iss=None),
        make_token(azp=None),
        make_token(azp=""),
        make_token(azp=42),
        make_token(exp=None),
        make_token(exp="tomorrow"),
        make_token(exp=int(time.time()) - 1),
    ],
    ids=[
        "empty",
        "garbage",
        "three-letters",
        "access-token",
        "id-token",
        "offline-token",
        "no-typ",
        "other-realm",
        "no-iss",
        "no-azp",
        "empty-azp",
        "azp-not-text",
        "no-exp",
        "exp-not-number",
        "expired",
    ],
)
def test_anything_else_is_a_401(token: str) -> None:
    with pytest.raises(UnauthorizedException) as info:
        inspect_refresh_token(token, issuer=ISSUER)

    assert info.value.status == 401
    assert info.value.detail == "The refresh token is invalid or has expired."


def test_expiry_uses_the_injected_clock() -> None:
    token = make_token(exp=2000)

    assert inspect_refresh_token(token, issuer=ISSUER, clock=lambda: 1999.0).client_id == "web-spa"
    with pytest.raises(UnauthorizedException):
        inspect_refresh_token(token, issuer=ISSUER, clock=lambda: 2000.0)


def test_the_reason_is_logged_but_the_token_never_is(caplog: pytest.LogCaptureFixture) -> None:
    token = make_token(typ="Bearer")

    with caplog.at_level(logging.DEBUG), pytest.raises(UnauthorizedException):
        inspect_refresh_token(token, issuer=ISSUER)

    assert "typ is not Refresh" in caplog.text
    assert token not in caplog.text
