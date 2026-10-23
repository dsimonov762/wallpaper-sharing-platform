"""Integration fixtures: a real Postgres (from `just infra-up`) and its migrated schema."""

from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from media.config.settings import get_settings
from media.repository.database import create_engine


@pytest.fixture
async def engine() -> AsyncGenerator[AsyncEngine]:
    get_settings.cache_clear()  # read the real .env, not a value cached by an earlier test
    engine = create_engine(get_settings())
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """A session whose work is rolled back at the end, so tests leave no rows behind.

    The session joins one outer transaction. Tests only `flush()` (send SQL, do not commit),
    and the outer transaction is rolled back when the test ends.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(bind=connection, expire_on_commit=False) as session:
            yield session
        await transaction.rollback()
