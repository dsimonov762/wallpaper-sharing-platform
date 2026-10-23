"""FastAPI dependencies: shared objects created in the lifespan and kept on app.state."""

from typing import Annotated, cast

from fastapi import Depends, Request
from redis.asyncio import Redis

from notification.config.settings import Settings


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


RedisDep = Annotated[Redis, Depends(get_redis)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
