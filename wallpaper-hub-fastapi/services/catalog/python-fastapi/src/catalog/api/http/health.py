"""Health endpoints. They move to the management port (8081) in a later slice."""

from fastapi import APIRouter, Request

from catalog.repository.database import MongoDatabase

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "UP"}


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    database: MongoDatabase = request.app.state.database
    await database.ping()  # raises 503 problem+json when MongoDB is down
    return {"status": "UP"}
