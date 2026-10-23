"""Integration-test fixtures: need a running Redis (just infra-up) and a .env file."""

from collections.abc import AsyncIterator
from typing import cast

import pytest
import pytest_asyncio
from pydantic import ValidationError
from redis.asyncio import Redis

from notification.config.settings import Settings
from notification.infra.redis_client import create_redis_client, ping_redis

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def real_settings() -> Settings:
    try:
        return Settings()  # pyright: ignore[reportCallIssue]
    except ValidationError as exc:
        pytest.fail(
            "Integration tests need NOTIFICATION_REDIS_URL. Copy .env.example to .env "
            f"(next to pyproject.toml) and adjust it.\n{exc}"
        )


@pytest_asyncio.fixture
async def redis(real_settings: Settings) -> AsyncIterator[Redis]:
    client = create_redis_client(real_settings)
    if not await ping_redis(client, timeout_seconds=2.0):
        await client.aclose()
        pytest.fail("Redis is not reachable. Start it with: just infra-up")
    try:
        yield client
    finally:
        await _delete_test_keys(client)
        await client.aclose()


async def _delete_test_keys(client: Redis) -> None:
    # KEYS is fine here: a dev Redis holds few keys. Production code must use SCAN.
    keys = cast(list[str], await client.keys("it:*"))  # pyright: ignore[reportUnknownMemberType]
    if keys:
        await client.delete(*keys)  # pyright: ignore[reportUnknownMemberType]
