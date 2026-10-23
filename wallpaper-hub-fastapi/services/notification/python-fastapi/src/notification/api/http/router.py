"""Collects all routers. Later slices add /api/v1 routes here."""

from fastapi import APIRouter

from notification.api.http import health


def build_router() -> APIRouter:
    router = APIRouter()
    router.include_router(health.router)
    return router
