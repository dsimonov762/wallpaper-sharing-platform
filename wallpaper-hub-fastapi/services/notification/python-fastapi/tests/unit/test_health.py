from collections.abc import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from redis.exceptions import ConnectionError as RedisConnectionError

from notification.api.http.dependencies import get_app_settings
from notification.config.settings import Settings
from notification.main import create_app

DEAD_REDIS = SecretStr("redis://127.0.0.1:1/0")  # nothing listens on port 1


def test_live_is_up(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_ready_is_up_when_redis_answers(
    client: TestClient, fake_redis: Callable[..., None]
) -> None:
    fake_redis()

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "UP", "checks": {"redis": "UP"}}


def test_ready_is_503_when_redis_fails(client: TestClient, fake_redis: Callable[..., None]) -> None:
    fake_redis(error=RedisConnectionError("connection refused"))

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "DOWN", "checks": {"redis": "DOWN"}}


def test_ready_does_not_leak_error_details(
    client: TestClient, fake_redis: Callable[..., None]
) -> None:
    fake_redis(error=RedisConnectionError("10.0.0.7:6379 refused"))

    response = client.get("/health/ready")

    assert "10.0.0.7" not in response.text


def test_ready_is_503_when_redis_is_too_slow(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    fake_redis: Callable[..., None],
) -> None:
    fast_timeout = settings.model_copy(update={"health_check_timeout_seconds": 0.05})
    app.dependency_overrides[get_app_settings] = lambda: fast_timeout
    fake_redis(delay_seconds=1.0)

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"] == {"redis": "DOWN"}


@pytest.mark.parametrize("path", ["/health/live", "/health/ready"])
def test_health_needs_no_token(
    client: TestClient, fake_redis: Callable[..., None], path: str
) -> None:
    fake_redis()

    assert client.get(path).status_code == 200


def test_ready_with_real_client_and_nothing_listening(
    make_settings: Callable[..., Settings],
) -> None:
    """Real Redis client against a closed port: no server needed, the answer must be 503."""
    dead = make_settings(
        redis_url=DEAD_REDIS,
        redis_connect_timeout_seconds=0.2,
        health_check_timeout_seconds=1.0,
    )

    with TestClient(create_app(dead)) as client:
        response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "DOWN", "checks": {"redis": "DOWN"}}


def test_service_starts_without_redis(make_settings: Callable[..., Settings]) -> None:
    """The lifespan must not connect: /health/live works while Redis is unreachable."""
    dead = make_settings(redis_url=DEAD_REDIS)

    with TestClient(create_app(dead)) as client:
        assert client.get("/health/live").status_code == 200
