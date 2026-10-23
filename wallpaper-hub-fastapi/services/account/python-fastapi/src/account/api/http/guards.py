"""Layer 1 of authorization (README section 7): protecting endpoints.

Three kinds of endpoint:

* public          -> no dependency at all (e.g. registration)
* authenticated   -> ``CurrentUserDep`` (any valid token)
* restricted      -> ``Depends(require_permission(...))``, ``Depends(require_role(...))``
                     or ``InternalDep`` (service-to-service only)

Order of answers: no/bad token -> 401 (from ``get_current_user``), valid token but not
allowed -> 403 (from here).
"""

import logging
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends

from account.api.http.dependencies import CurrentUserDep
from account.domain.exceptions import ForbiddenException
from account.security.current_user import CurrentUser
from account.security.permissions import INTERNAL_ROLE, Permission

logger = logging.getLogger(__name__)

Guard = Callable[[CurrentUser], Awaitable[CurrentUser]]


def _deny(user: CurrentUser, needed: str) -> ForbiddenException:
    logger.info("Access denied for %s: needs %s", user.id, needed)
    return ForbiddenException("You do not have permission to perform this action.")


def require_permission(permission: Permission) -> Guard:
    """Dependency factory: the caller must hold ``permission``."""

    async def guard(user: CurrentUserDep) -> CurrentUser:
        if not user.has_permission(permission):
            raise _deny(user, permission.value)
        return user

    return guard


def require_role(*roles: str) -> Guard:
    """Dependency factory: the caller must hold at least one of ``roles``.

    Prefer ``require_permission``; use this only when a role itself is the rule.
    """

    async def guard(user: CurrentUserDep) -> CurrentUser:
        if not any(user.has_role(role) for role in roles):
            raise _deny(user, "role " + "|".join(roles))
        return user

    return guard


async def require_internal(user: CurrentUserDep) -> CurrentUser:
    """Internal-only endpoints: callable by service accounts, never by end users."""
    if not user.has_role(INTERNAL_ROLE):
        raise _deny(user, f"role {INTERNAL_ROLE}")
    return user


InternalDep = Annotated[CurrentUser, Depends(require_internal)]
