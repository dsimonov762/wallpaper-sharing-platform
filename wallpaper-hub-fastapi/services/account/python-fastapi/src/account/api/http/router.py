"""Everything under /api/v1."""

from fastapi import APIRouter

from account.api.http import auth, registrations, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(registrations.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
