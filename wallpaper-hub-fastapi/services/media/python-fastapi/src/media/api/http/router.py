"""Collects every `/api/v1` router. The media endpoints are added in the next slices."""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")
