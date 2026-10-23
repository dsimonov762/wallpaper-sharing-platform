"""Wallpaper request and response DTOs."""

from datetime import datetime
from typing import Annotated, Self

from pydantic import BeforeValidator, Field, StringConstraints, field_validator, model_validator

from catalog.domain.models import Category, WallpaperStatus
from catalog.dto.base import ApiModel, ApiRequest

MAX_TAGS = 10

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


def _normalize_tag(value: object) -> object:
    """Runs BEFORE the constraints: pydantic checks the pattern on the raw text otherwise."""
    return value.strip().lower() if isinstance(value, str) else value


Tag = Annotated[
    str,
    BeforeValidator(_normalize_tag),
    StringConstraints(min_length=1, max_length=30, pattern=r"^[a-z0-9-]+$"),
]
AssetId = Annotated[str, StringConstraints(pattern=r"^ast_[0-9A-Za-z]{10,40}$")]
UserId = Annotated[str, StringConstraints(min_length=1, max_length=64)]


def _dedupe(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(tags))


class CreateWallpaperRequest(ApiRequest):
    title: Title
    description: Description = ""
    tags: Annotated[list[Tag], Field(max_length=MAX_TAGS)] = Field(default_factory=list[str])
    category: Category
    asset_id: AssetId
    # TEMPORARY (removed in step C2): the owner will come from the token's `sub` claim.
    author_id: UserId

    @field_validator("tags")
    @classmethod
    def _unique_tags(cls, tags: list[str]) -> list[str]:
        return _dedupe(tags)


class UpdateWallpaperRequest(ApiRequest):
    """PATCH body. Only sent fields change; null is treated like 'not sent'."""

    title: Title | None = None
    description: Description | None = None
    tags: Annotated[list[Tag], Field(max_length=MAX_TAGS)] | None = None
    category: Category | None = None

    @field_validator("tags")
    @classmethod
    def _unique_tags(cls, tags: list[str] | None) -> list[str] | None:
        return None if tags is None else _dedupe(tags)

    @model_validator(mode="after")
    def _at_least_one_field(self) -> Self:
        if not any(
            value is not None for value in (self.title, self.description, self.tags, self.category)
        ):
            msg = "At least one field must be provided."
            raise ValueError(msg)
        return self


class AuthorResponse(ApiModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None


class VariantResponse(ApiModel):
    kind: str
    url: str
    width: int
    height: int


class DimensionsResponse(ApiModel):
    width: int
    height: int


class WallpaperResponse(ApiModel):
    id: str
    title: str
    description: str
    tags: list[str]
    category: Category
    status: WallpaperStatus
    asset_id: str
    variants: list[VariantResponse]
    dimensions: DimensionsResponse | None
    palette: list[str]
    blurhash: str | None
    author: AuthorResponse
    favorite_count: int
    created_at: datetime
    updated_at: datetime
    version: int
