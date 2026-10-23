"""Application entry point: builds the FastAPI app.

Bootstrap order (README section 12). Done so far: config -> database pool.
Still to come: logging+telemetry -> token validation -> DI wiring -> HTTP/management
-> workers/schedulers -> graceful shutdown.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from media.api.http.errors import register_exception_handlers
from media.api.http.health import router as health_router
from media.api.http.router import api_router
from media.config.settings import get_settings
from media.repository.database import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    settings = get_settings()  # fail fast: invalid configuration stops startup here
    engine = create_engine(settings)  # lazy: the service starts even if the DB is down
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        await engine.dispose()  # close pooled connections on shutdown


def create_app() -> FastAPI:
    app = FastAPI(title="Wallpaper Hub - media-service", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router)
    return app


app = create_app()
