"""Explicit field-by-field mapping between DTOs and domain objects."""

from catalog.domain.models import CreateWallpaper, Wallpaper, WallpaperChanges
from catalog.dto.wallpaper import (
    AuthorResponse,
    CreateWallpaperRequest,
    DimensionsResponse,
    UpdateWallpaperRequest,
    VariantResponse,
    WallpaperResponse,
)


def to_create_command(request: CreateWallpaperRequest) -> CreateWallpaper:
    return CreateWallpaper(
        title=request.title,
        description=request.description,
        tags=request.tags,
        category=request.category,
        asset_id=request.asset_id,
        author_id=request.author_id,
    )


def to_changes(request: UpdateWallpaperRequest) -> WallpaperChanges:
    return WallpaperChanges(
        title=request.title,
        description=request.description,
        tags=request.tags,
        category=request.category,
    )


def to_response(wallpaper: Wallpaper) -> WallpaperResponse:
    dims = wallpaper.dimensions
    return WallpaperResponse(
        id=wallpaper.id,
        title=wallpaper.title,
        description=wallpaper.description,
        tags=list(wallpaper.tags),
        category=wallpaper.category,
        status=wallpaper.status,
        asset_id=wallpaper.asset_id,
        variants=[
            VariantResponse(kind=v.kind, url=v.url, width=v.width, height=v.height)
            for v in wallpaper.variants
        ],
        dimensions=None
        if dims is None
        else DimensionsResponse(width=dims.width, height=dims.height),
        palette=list(wallpaper.palette),
        blurhash=wallpaper.blurhash,
        author=AuthorResponse(
            id=wallpaper.author.id,
            username=wallpaper.author.username,
            display_name=wallpaper.author.display_name,
            avatar_url=wallpaper.author.avatar_url,
        ),
        favorite_count=wallpaper.favorite_count,
        created_at=wallpaper.created_at,
        updated_at=wallpaper.updated_at,
        version=wallpaper.version,
    )
