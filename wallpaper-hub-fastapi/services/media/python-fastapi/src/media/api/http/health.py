"""Health endpoints (README section 11): is the process alive, and can it do its job?"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from media.api.http.dependencies import get_engine
from media.repository.database import database_is_reachable

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    """Liveness: the process is running. It must not check dependencies."""
    return {"status": "UP"}


@router.get(
    "/ready",
    responses={HTTPStatus.SERVICE_UNAVAILABLE.value: {"description": "A dependency is down"}},
)
async def ready(engine: Annotated[AsyncEngine, Depends(get_engine)]) -> JSONResponse:
    """Readiness: the dependencies this service needs are reachable (Postgres for now)."""
    postgres_up = await database_is_reachable(engine)
    body = {
        "status": "UP" if postgres_up else "DOWN",
        "checks": {"postgres": "UP" if postgres_up else "DOWN"},
    }
    status = HTTPStatus.OK if postgres_up else HTTPStatus.SERVICE_UNAVAILABLE
    return JSONResponse(body, status_code=status.value)
