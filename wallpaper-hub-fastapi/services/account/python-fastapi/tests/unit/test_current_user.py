"""CurrentUser.from_claims: reading the caller out of an already-verified token."""

from typing import Any

import pytest

from account.security.current_user import CurrentUser


def test_full_keycloak_style_claims() -> None:
    user = CurrentUser.from_claims(
        {
            "sub": "u-1",
            "email": "alice@example.com",
            "locale": "de",
            "realm_access": {"roles": ["USER", "MODERATOR", "offline_access"]},
            "scope": "openid email profile",
        }
    )
    assert user.id == "u-1"
    assert user.email == "alice@example.com"
    assert user.locale == "de"
    assert user.roles == {"USER", "MODERATOR", "offline_access"}
    assert user.scope == {"openid", "email", "profile"}
    assert user.has_role("MODERATOR")
    assert not user.has_role("ADMIN")


def test_service_account_token_without_email_or_locale() -> None:
    user = CurrentUser.from_claims({"sub": "svc-1", "realm_access": {"roles": ["internal"]}})
    assert user.email is None
    assert user.locale is None
    assert user.roles == {"internal"}
    assert user.scope == frozenset()


@pytest.mark.parametrize(
    "claims",
    [
        {"sub": "u-1"},
        {"sub": "u-1", "realm_access": None},
        {"sub": "u-1", "realm_access": "ADMIN"},
        {"sub": "u-1", "realm_access": {"roles": "ADMIN"}},
        {"sub": "u-1", "realm_access": {"roles": [1, None, {"a": 1}]}},
    ],
)
def test_missing_or_malformed_roles_mean_no_roles(claims: dict[str, Any]) -> None:
    assert CurrentUser.from_claims(claims).roles == frozenset()


def test_odd_value_types_are_ignored_not_trusted() -> None:
    user = CurrentUser.from_claims({"sub": "u-1", "email": 42, "locale": "", "scope": ["openid"]})
    assert user.email is None
    assert user.locale is None
    assert user.scope == frozenset()
