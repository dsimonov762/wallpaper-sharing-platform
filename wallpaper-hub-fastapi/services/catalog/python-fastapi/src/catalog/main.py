"""App factory and lifespan. Run: uvicorn catalog.main:create_app --factory --port 8082"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from catalog.api.http import health
from catalog.api.http.errors import register_exception_handlers
from catalog.api.http.router import api_router
from catalog.config.settings import Settings, get_settings
from catalog.infra.author_directory_factory import create_author_directory
from catalog.repository.database import create_mongo_database
from catalog.repository.wallpaper_repository import MongoWallpaperRepository


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings: Settings = app.state.settings
    database = create_mongo_database(settings)
    app.state.database = database
    app.state.wallpaper_store = MongoWallpaperRepository(database.wallpapers)
    app.state.author_directory = create_author_directory(settings)
    try:
        yield
    finally:
        await database.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Wallpaper Hub catalog-service", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings or get_settings()
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(api_router)
    return app
