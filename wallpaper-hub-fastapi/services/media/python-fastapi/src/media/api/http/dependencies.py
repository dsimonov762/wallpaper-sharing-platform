"""Small FastAPI dependencies: they hand objects created at startup to the route functions."""

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine


def get_engine(request: Request) -> AsyncEngine:
    """The connection pool built in `main.lifespan`. Tests replace this with a fake."""
    engine: AsyncEngine = request.app.state.engine
    return engine
