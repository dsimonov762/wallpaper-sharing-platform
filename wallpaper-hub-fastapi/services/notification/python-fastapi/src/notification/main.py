"""Application factory and lifespan. Start with: uvicorn notification.main:create_app --factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from notification import __version__
from notification.api.http.errors import register_exception_handlers
from notification.api.http.router import build_router
from notification.config.settings import Settings, get_settings
from notification.infra.redis_client import create_redis_client


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # Startup: build shared objects once. Redis connects lazily, so the service
        # starts even when Redis is down; /health/ready reports it.
        redis = create_redis_client(resolved)
        app.state.settings = resolved
        app.state.redis = redis
        try:
            yield
        finally:
            # Shutdown: release connections.
            await redis.aclose()

    app = FastAPI(
        title="Wallpaper Hub notification-service",
        version=__version__,
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(build_router())
    return app
