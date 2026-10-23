"""Layer 3 of authorization (README section 7): ownership checks.

A permission says "users may delete accounts"; ownership says "...their OWN account".
The rule used here: allowed if you own the thing, or you hold a permission that
overrides ownership (for example an ADMIN may delete anyone).

Note: ``CurrentUser.id`` is the token's ``sub``, so it only matches ``users.id`` if the
user row uses Keycloak's id as its primary key. Step 3.6 makes that true.
"""

from uuid import UUID

from account.domain.exceptions import ForbiddenException
from account.security.current_user import CurrentUser
from account.security.permissions import Permission


def is_owner(user: CurrentUser, owner_id: str | UUID) -> bool:
    return user.id == str(owner_id)


def ensure_owner_or_permission(
    user: CurrentUser, owner_id: str | UUID, override: Permission
) -> None:
    """Raise ``ForbiddenException`` unless ``user`` owns the resource or holds ``override``."""
    if is_owner(user, owner_id) or user.has_permission(override):
        return
    raise ForbiddenException("You are not allowed to access this resource.")
