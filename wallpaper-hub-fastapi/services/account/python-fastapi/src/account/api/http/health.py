"""Health endpoints. Later they move to the management port (8081)."""

from fastapi import APIRouter, Response, status

from account.api.http.dependencies import EngineDep
from account.repository.database import database_is_reachable

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    """Liveness: the process is running. Never checks dependencies (a DB outage must not
    make the orchestrator restart a healthy process)."""
    return {"status": "UP"}


@router.get("/ready")
async def ready(engine: EngineDep, response: Response) -> dict[str, object]:
    """Readiness: can this instance serve traffic? 503 tells load balancers to wait."""
    database_up = await database_is_reachable(engine)
    if not database_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "UP" if database_up else "DOWN",
        "checks": {"database": "UP" if database_up else "DOWN"},
    }
