"""FastAPI dependencies: build the service from what the lifespan put on app.state."""

from typing import Annotated

from fastapi import Depends, Request

from catalog.domain.ports import AuthorDirectory, WallpaperStore
from catalog.domain.wallpaper_service import WallpaperService


def get_wallpaper_service(request: Request) -> WallpaperService:
    store: WallpaperStore = request.app.state.wallpaper_store
    authors: AuthorDirectory = request.app.state.author_directory
    return WallpaperService(store=store, authors=authors)


WallpaperServiceDep = Annotated[WallpaperService, Depends(get_wallpaper_service)]
