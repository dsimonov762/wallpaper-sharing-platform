"""Liveness and readiness (README section 11). On the main port until the management port exists."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from notification.api.http.dependencies import RedisDep, SettingsDep
from notification.dto.health import HealthResponse
from notification.infra.redis_client import ping_redis

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model_exclude_none=True, summary="Is the process running?")
async def live() -> HealthResponse:
    """Always UP while the process can answer. Never touches a dependency."""
    return HealthResponse(status="UP")


@router.get(
    "/ready",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
    summary="Can the service do its work? Checks Redis.",
)
async def ready(redis: RedisDep, settings: SettingsDep) -> HealthResponse | JSONResponse:
    """200 when Redis answers, 503 when it does not. The body names the failing check only."""
    redis_up = await ping_redis(redis, settings.health_check_timeout_seconds)
    report = HealthResponse(
        status="UP" if redis_up else "DOWN",
        checks={"redis": "UP" if redis_up else "DOWN"},
    )
    if redis_up:
        return report
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=report.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
