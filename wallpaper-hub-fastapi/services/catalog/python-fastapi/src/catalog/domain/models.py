"""Domain model. Shape follows README 6.3 (the Mongo document)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class WallpaperStatus(StrEnum):
    PENDING_MEDIA = "PENDING_MEDIA"
    PUBLISHED = "PUBLISHED"
    REJECTED = "REJECTED"


class Category(StrEnum):
    NATURE = "NATURE"
    ABSTRACT = "ABSTRACT"
    CITY = "CITY"
    SPACE = "SPACE"
    ANIMALS = "ANIMALS"
    MINIMAL = "MINIMAL"
    GAMES = "GAMES"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class Author:
    """Denormalized snapshot of the account (README 4.2): copied, not referenced."""

    id: str
    username: str
    display_name: str
    avatar_url: str | None


@dataclass(frozen=True, slots=True)
class Variant:
    kind: str
    url: str
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Dimensions:
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Wallpaper:
    id: str
    title: str
    description: str
    tags: list[str]
    category: Category
    status: WallpaperStatus
    asset_id: str
    author: Author
    created_at: datetime
    updated_at: datetime
    version: int
    favorite_count: int = 0
    # Filled later by the media.asset.processed event (step C7); empty until then.
    variants: list[Variant] = field(default_factory=list[Variant])
    dimensions: Dimensions | None = None
    palette: list[str] = field(default_factory=list[str])
    blurhash: str | None = None


@dataclass(frozen=True, slots=True)
class CreateWallpaper:
    title: str
    description: str
    tags: list[str]
    category: Category
    asset_id: str
    author_id: str


@dataclass(frozen=True, slots=True)
class WallpaperChanges:
    """Only the fields that were sent. None means 'leave as it is'."""

    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    category: Category | None = None
