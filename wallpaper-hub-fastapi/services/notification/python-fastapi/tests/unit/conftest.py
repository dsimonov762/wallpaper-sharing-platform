"""Unit-test fixtures. No Redis, no network: Redis is replaced by a fake."""

import asyncio
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from notification.api.http.dependencies import get_redis
from notification.config.settings import Settings
from notification.main import create_app


class FakeRedis:
    """Stands in for the Redis client: answers PING, fails, or answers too slowly."""

    def __init__(self, *, error: Exception | None = None, delay_seconds: float = 0.0) -> None:
        self.error = error
        self.delay_seconds = delay_seconds

    async def ping(self) -> bool:
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        if self.error is not None:
            raise self.error
        return True


@pytest.fixture
def make_settings() -> Callable[..., Settings]:
    """Factory for Settings that never read a real .env file (_env_file=None)."""

    def build(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "environment": "test",
            "redis_url": SecretStr("redis://localhost:6379/0"),
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]

    return build


@pytest.fixture
def settings(make_settings: Callable[..., Settings]) -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # raise_server_exceptions=False: an unexpected error becomes a 500 answer, as in production.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def fake_redis(app: FastAPI) -> Callable[..., None]:
    """Call fake_redis() to make the app talk to a FakeRedis. Options: error=, delay_seconds=."""

    def install(*, error: Exception | None = None, delay_seconds: float = 0.0) -> None:
        fake = FakeRedis(error=error, delay_seconds=delay_seconds)
        app.dependency_overrides[get_redis] = lambda: fake

    return install
