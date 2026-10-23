"""Talks to the real Redis from .env. Test keys start with 'it:' and are deleted afterwards."""

import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis.asyncio import Redis

from notification.config.settings import Settings
from notification.main import create_app

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_client_round_trip_returns_text(redis: Redis) -> None:
    key = f"it:{uuid.uuid4().hex}"

    await redis.set(key, "hello", ex=30)  # pyright: ignore[reportUnknownMemberType]
    value = await redis.get(key)  # pyright: ignore[reportUnknownMemberType]

    assert value == "hello"  # str, not bytes: decode_responses=True


@pytest.mark.asyncio
async def test_expiry_is_applied(redis: Redis) -> None:
    key = f"it:{uuid.uuid4().hex}"

    await redis.set(key, "x", ex=30)  # pyright: ignore[reportUnknownMemberType]
    ttl = await redis.ttl(key)  # pyright: ignore[reportUnknownMemberType]

    assert 0 < ttl <= 30


def test_ready_is_up_against_real_redis(real_settings: Settings, redis: Redis) -> None:
    # `redis` is requested only so the test fails early with a clear message if Redis is down.
    with TestClient(create_app(real_settings)) as client:
        response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "checks": {"redis": "UP"}}


def test_ready_is_503_when_pointed_at_a_dead_port(real_settings: Settings) -> None:
    dead = real_settings.model_copy(
        update={
            "redis_url": SecretStr("redis://127.0.0.1:1/0"),
            "redis_connect_timeout_seconds": 0.2,
        }
    )

    with TestClient(create_app(dead)) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
