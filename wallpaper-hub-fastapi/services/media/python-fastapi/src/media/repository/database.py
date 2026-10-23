"""Database engine, session factory and a reachability check (SQLAlchemy async + asyncpg)."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from media.config.settings import Settings

logger = logging.getLogger(__name__)


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the connection pool. No connection is opened until the first query."""
    return create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        pool_pre_ping=True,  # test a pooled connection before using it (survives DB restarts)
        connect_args={"timeout": settings.db_connect_timeout_s},
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """A session = one unit of work (a transaction). Create one per request."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def database_is_reachable(engine: AsyncEngine) -> bool:
    """Used by /health/ready: can we run `SELECT 1`?"""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError):
        logger.warning("Database readiness check failed", exc_info=True)
        return False
    return True
