from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from notification.config.settings import Settings


def make(**values: Any) -> Settings:
    return Settings(_env_file=None, **values)  # pyright: ignore[reportCallIssue]


def test_redis_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NOTIFICATION_REDIS_URL", raising=False)

    with pytest.raises(ValidationError) as caught:
        make()

    assert "redis_url" in str(caught.value)


def test_reads_prefixed_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATION_REDIS_URL", "redis://example:6380/2")
    monkeypatch.setenv("NOTIFICATION_ENVIRONMENT", "prod")

    settings = make()

    assert settings.redis_url.get_secret_value() == "redis://example:6380/2"
    assert settings.environment == "prod"


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFICATION_REDIS_URL", "redis://localhost:6379/0")

    settings = make()

    assert settings.environment == "local"
    assert settings.redis_connect_timeout_seconds == 1.0
    assert settings.redis_command_timeout_seconds == 2.0
    assert settings.health_check_timeout_seconds == 1.0


@pytest.mark.parametrize("url", ["localhost:6379", "http://localhost:6379", ""])
def test_rejects_unknown_url_scheme(url: str) -> None:
    with pytest.raises(ValidationError):
        make(redis_url=SecretStr(url))


@pytest.mark.parametrize("url", ["redis://h:6379/0", "rediss://h:6380/0", "unix:///tmp/redis.sock"])
def test_accepts_known_url_schemes(url: str) -> None:
    assert make(redis_url=SecretStr(url)).redis_url.get_secret_value() == url


def test_password_is_not_shown_in_repr() -> None:
    settings = make(redis_url=SecretStr("redis://:s3cret@localhost:6379/0"))

    assert "s3cret" not in repr(settings)
    assert "s3cret" not in str(settings)


@pytest.mark.parametrize(
    "name",
    [
        "redis_connect_timeout_seconds",
        "redis_command_timeout_seconds",
        "health_check_timeout_seconds",
    ],
)
def test_timeouts_must_be_positive(name: str) -> None:
    with pytest.raises(ValidationError):
        make(redis_url=SecretStr("redis://localhost:6379/0"), **{name: 0})
