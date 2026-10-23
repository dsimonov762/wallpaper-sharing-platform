"""Redis connection factory and a small readiness probe."""

import asyncio
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from notification.config.settings import Settings

logger = logging.getLogger(__name__)


def create_redis_client(settings: Settings) -> Redis:
    """Build the one shared async client. It connects lazily, on the first command.

    decode_responses=True makes Redis return str instead of bytes.
    """
    # redis-py types its connection kwargs loosely, hence the ignore.
    return Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        settings.redis_url.get_secret_value(),
        decode_responses=True,
        socket_connect_timeout=settings.redis_connect_timeout_seconds,
        socket_timeout=settings.redis_command_timeout_seconds,
    )


async def ping_redis(client: Redis, timeout_seconds: float) -> bool:
    """True if Redis answers PING within the time limit. Never raises."""
    try:
        async with asyncio.timeout(timeout_seconds):
            await client.ping()  # pyright: ignore[reportUnknownMemberType]
    except (RedisError, OSError, TimeoutError) as exc:
        logger.warning("Redis readiness check failed: %s", type(exc).__name__)
        return False
    return True
