"""Layer 2 of authorization (README section 7): roles are mapped to permissions.

Keycloak tells us WHO has WHICH role. This file decides what each role may DO in
account-service. Code checks permissions ("may this caller list users?"), never role
names, so changing who may do what means editing one table here.

Permission names are ``resource:action``. README examples such as ``wallpaper:write``
belong to catalog-service and live in its own table later.
"""

from collections.abc import Iterable
from enum import StrEnum


class Permission(StrEnum):
    PROFILE_READ = "profile:read"
    PROFILE_WRITE = "profile:write"
    USER_READ = "user:read"
    USER_LIST = "user:list"
    USER_DELETE = "user:delete"
    INTERNAL_CALL = "internal:call"


INTERNAL_ROLE = "internal"  # held by service accounts (README section 7)

_USER_PERMISSIONS = frozenset(
    {Permission.PROFILE_READ, Permission.PROFILE_WRITE, Permission.USER_READ}
)

# Realm roles are NOT inherited automatically: the demo admin holds USER, MODERATOR and ADMIN
# together, and a user's permissions are the union over all of their roles.
ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "USER": _USER_PERMISSIONS,
    # MODERATOR powers (wallpaper:moderate) matter in catalog-service, not here.
    "MODERATOR": _USER_PERMISSIONS,
    "ADMIN": _USER_PERMISSIONS | {Permission.USER_LIST, Permission.USER_DELETE},
    INTERNAL_ROLE: frozenset({Permission.INTERNAL_CALL, Permission.USER_READ}),
}


def permissions_for(roles: Iterable[str]) -> frozenset[Permission]:
    """All permissions granted by ``roles``. Unknown roles (``offline_access``...) grant nothing."""
    granted: set[Permission] = set()
    for role in roles:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    return frozenset(granted)
