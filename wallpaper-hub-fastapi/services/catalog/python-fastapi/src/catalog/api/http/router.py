from fastapi import APIRouter

from catalog.api.http import wallpapers

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(wallpapers.router)
