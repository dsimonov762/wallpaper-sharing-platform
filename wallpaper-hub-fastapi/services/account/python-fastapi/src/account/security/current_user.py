"""``CurrentUser``: the caller, as described by an already-verified access token.

This module only reads claims. Signature and expiry were checked earlier by
``TokenValidator``; nothing here touches the network or FastAPI.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Self, cast

from account.security.permissions import Permission, permissions_for


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _text_set(values: object) -> frozenset[str]:
    if not isinstance(values, list):
        return frozenset()
    return frozenset(item for item in cast(list[object], values) if isinstance(item, str))


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: str  # the `sub` claim: Keycloak's id for this user (or service account)
    email: str | None
    locale: str | None
    roles: frozenset[str]  # realm roles such as USER, MODERATOR, ADMIN (or `internal`)
    scope: frozenset[str]

    @classmethod
    def from_claims(cls, claims: Mapping[str, Any]) -> Self:
        realm_access = claims.get("realm_access")
        roles = (
            _text_set(cast(dict[str, object], realm_access).get("roles"))
            if isinstance(realm_access, dict)
            else frozenset[str]()
        )
        scope = claims.get("scope")
        return cls(
            id=str(claims["sub"]),
            email=_text(claims.get("email")),
            locale=_text(claims.get("locale")),
            roles=roles,
            scope=frozenset(scope.split()) if isinstance(scope, str) else frozenset(),
        )

    def has_role(self, role: str) -> bool:
        return role in self.roles

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for(self.roles)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions
