"""Business logic for users. Knows nothing about HTTP or SQL syntax."""

import logging
from dataclasses import dataclass
from typing import TypedDict
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from account.domain.exceptions import (
    ConflictException,
    FieldIssue,
    NotFoundException,
    PreconditionFailedException,
)
from account.domain.identity import IdentityProvider
from account.repository.models import UserEntity
from account.repository.user_repository import SORTABLE_FIELDS, UserRepository
from account.util.clock import utc_now
from account.util.pagination import PageResult, parse_sort

logger = logging.getLogger(__name__)

_ALREADY_EXISTS = {
    "username": FieldIssue("username", "AlreadyExists", "This username is already taken."),
    "email": FieldIssue("email", "AlreadyExists", "This email address is already registered."),
}


@dataclass(frozen=True)
class Registration:
    username: str
    email: str
    password: SecretStr
    display_name: str | None
    locale: str


class ProfileChanges(TypedDict, total=False):
    """The profile fields a user may edit. A key that is absent means "leave it alone"."""

    display_name: str
    bio: str | None  # None clears the bio
    locale: str


class UserService:
    def __init__(
        self, session: AsyncSession, users: UserRepository, identity: IdentityProvider
    ) -> None:
        self._session = session
        self._users = users
        self._identity = identity

    async def register(self, registration: Registration) -> UserEntity:
        """Create the login identity, then the profile row.

        The two live in different systems and cannot share one transaction. If the database
        step fails after the identity exists, we undo the identity (a "compensating action"),
        otherwise the username would stay blocked in Keycloak with no profile behind it.
        """
        taken = await self._users.username_or_email_taken(registration.username, registration.email)
        if taken:
            raise ConflictException(
                "The user already exists.", [_ALREADY_EXISTS[f] for f in sorted(taken)]
            )

        user_id = await self._identity.create_user(
            username=registration.username,
            email=registration.email,
            password=registration.password,
        )
        user = UserEntity(
            id=user_id,
            username=registration.username,
            email=registration.email,
            display_name=registration.display_name or registration.username,
            locale=registration.locale,
        )
        try:
            await self._users.add(user)
            await self._session.commit()
        except Exception as error:
            await self._session.rollback()
            await self._remove_identity(user_id)
            if isinstance(error, IntegrityError):
                # Two requests can pass the check above at the same moment; the database
                # constraints are the real guarantee, so translate their failure too.
                raise _conflict_from(error) from error
            raise
        return user

    async def _remove_identity(self, user_id: UUID) -> None:
        """Undo `create_user`. Never raises: the original error matters more than this cleanup."""
        try:
            await self._identity.delete_user(user_id)
        except Exception:
            logger.error(
                "Registration failed and identity %s could not be removed; delete it by hand",
                user_id,
                exc_info=True,
            )

    async def get(self, user_id: UUID) -> UserEntity:
        user = await self._users.get(user_id)
        if user is None:
            raise NotFoundException(f"User {user_id} was not found.")
        return user

    async def list_users(self, page: int, size: int, sort: str) -> PageResult[UserEntity]:
        return await self._users.list_page(page, size, parse_sort(sort, SORTABLE_FIELDS))

    async def update_profile(
        self,
        user_id: UUID,
        changes: ProfileChanges,
        expected_versions: frozenset[int] | None,
    ) -> UserEntity:
        """Apply a partial profile edit, but only if the caller saw the current version.

        `expected_versions` are the versions the caller's If-Match header accepts;
        None means "any version" (`If-Match: *`).
        """
        user = await self.get(user_id)
        if expected_versions is not None and user.version not in expected_versions:
            raise _OUT_OF_DATE
        if "display_name" in changes:
            user.display_name = changes["display_name"]
        if "bio" in changes:
            user.bio = changes["bio"]
        if "locale" in changes:
            user.locale = changes["locale"]
        try:
            await self._session.commit()
        except StaleDataError as error:
            # Someone saved between our read and our write. The version column made the
            # UPDATE touch zero rows instead of silently overwriting their change.
            await self._session.rollback()
            raise _OUT_OF_DATE from error
        return user

    async def delete(self, user_id: UUID) -> None:
        """Soft delete: the row stays (for the 30-day purge job) but disappears from the API."""
        user = await self.get(user_id)
        user.deleted_at = utc_now()
        await self._session.commit()
        # Best effort: the profile is already gone from the API, so a failure here must not
        # turn the delete into an error. The purge job removes the identity for good later.
        try:
            await self._identity.disable_user(user_id)
        except Exception:
            logger.error("Could not disable the login of deleted user %s", user_id, exc_info=True)


_OUT_OF_DATE = PreconditionFailedException(
    "The profile was changed by someone else. Fetch it again and retry."
)


def _conflict_from(error: IntegrityError) -> ConflictException:
    message = str(error.orig)
    issues = [issue for field, issue in _ALREADY_EXISTS.items() if f"uq_users_{field}" in message]
    return ConflictException("The user already exists.", issues)
