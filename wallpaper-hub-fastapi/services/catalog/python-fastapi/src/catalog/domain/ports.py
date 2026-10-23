"""Ports: what the domain needs from the outside. Adapters live in repository/ and infra/."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol

from catalog.domain.models import Author, Category, Wallpaper, WallpaperStatus

SortField = Literal["createdAt", "updatedAt", "title", "favoriteCount"]
SortDirection = Literal["asc", "desc"]


@dataclass(frozen=True, slots=True)
class WallpaperFilter:
    status: WallpaperStatus | None = None
    category: Category | None = None
    tag: str | None = None
    author_id: str | None = None


@dataclass(frozen=True, slots=True)
class PageRequest:
    page: int
    size: int
    sort_field: SortField
    direction: SortDirection


class WallpaperStore(Protocol):
    async def insert(self, wallpaper: Wallpaper) -> None: ...

    async def get(self, wallpaper_id: str) -> Wallpaper | None: ...

    async def list(
        self, flt: WallpaperFilter, page: PageRequest
    ) -> tuple[list[Wallpaper], int]: ...

    async def update_if_version(
        self,
        wallpaper_id: str,
        expected_version: int,
        changes: Mapping[str, object],
        now: datetime,
    ) -> Wallpaper | None:
        """Apply changes only if the stored version still equals expected_version.

        Returns the new state, or None when nothing matched (missing or changed meanwhile).
        """
        ...


class AuthorDirectory(Protocol):
    async def get_author(self, user_id: str) -> Author: ...
