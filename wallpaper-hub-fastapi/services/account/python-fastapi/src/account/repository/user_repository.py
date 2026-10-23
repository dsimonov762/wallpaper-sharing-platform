"""All SQL for users. Nothing outside this file builds queries."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from account.repository.models import UserEntity
from account.util.pagination import PageResult, SortSpec

# API sort name -> column. This is the whitelist: anything else is rejected before SQL exists.
SORTABLE_FIELDS: dict[str, InstrumentedAttribute[Any]] = {
    "createdAt": UserEntity.created_at,
    "username": UserEntity.username,
    "displayName": UserEntity.display_name,
    "bio": UserEntity.bio,
}


class UserRepository:
    """Reads and writes users. It flushes but never commits: the service owns the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: UserEntity) -> None:
        self._session.add(user)
        await self._session.flush()  # sends the INSERT now, so constraint violations surface here

    async def get(self, user_id: UUID) -> UserEntity | None:
        statement = select(UserEntity).where(
            UserEntity.id == user_id, UserEntity.deleted_at.is_(None)
        )
        return await self._session.scalar(statement)

    async def username_or_email_taken(self, username: str, email: str) -> set[str]:
        """Returns which of {"username", "email"} already exist (soft-deleted users included)."""
        statement = select(UserEntity.username, UserEntity.email).where(
            (UserEntity.username == username) | (UserEntity.email == email)
        )
        taken: set[str] = set()
        for existing_username, existing_email in await self._session.execute(statement):
            if existing_username == username:
                taken.add("username")
            if existing_email == email:
                taken.add("email")
        return taken

    async def list_page(self, page: int, size: int, sort: SortSpec) -> PageResult[UserEntity]:
        active = UserEntity.deleted_at.is_(None)
        total = await self._session.scalar(
            select(func.count()).select_from(UserEntity).where(active)
        )
        column = SORTABLE_FIELDS[sort.field]
        direction = column.desc() if sort.descending else column.asc()
        order: Sequence[Any] = (direction.nulls_last(), UserEntity.id)
        statement = (
            select(UserEntity).where(active).order_by(*order).offset(page * size).limit(size)
        )  # id as tie-breaker keeps pages stable when the sort column has duplicates
        rows = await self._session.scalars(statement)
        return PageResult(items=list(rows), total=total or 0)
