"""Unit-test setup: fake environment (a real .env is never read) and an in-memory store."""

import os
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ["CATALOG_MONGODB_URI"] = "mongodb://unit-test.invalid:27017/catalog"
os.environ["CATALOG_ENVIRONMENT"] = "test"

from catalog.api.http.dependencies import get_wallpaper_service
from catalog.config.settings import Settings
from catalog.domain.models import Category, Wallpaper
from catalog.domain.ports import PageRequest, WallpaperFilter
from catalog.domain.wallpaper_service import WallpaperService
from catalog.infra.local_author_directory import LocalAuthorDirectory
from catalog.main import create_app


def _sort_value(w: Wallpaper, field: str) -> datetime | str | int:
    match field:
        case "createdAt":
            return w.created_at
        case "updatedAt":
            return w.updated_at
        case "title":
            return w.title
        case _:
            return w.favorite_count


class InMemoryWallpaperStore:
    """Fake WallpaperStore. Same contract as the Mongo repository, no database."""

    def __init__(self) -> None:
        self.items: dict[str, Wallpaper] = {}
        self.fail_next_update = False

    async def insert(self, wallpaper: Wallpaper) -> None:
        self.items[wallpaper.id] = wallpaper

    async def get(self, wallpaper_id: str) -> Wallpaper | None:
        return self.items.get(wallpaper_id)

    async def list(self, flt: WallpaperFilter, page: PageRequest) -> tuple[list[Wallpaper], int]:
        rows = [
            w
            for w in self.items.values()
            if (flt.status is None or w.status == flt.status)
            and (flt.category is None or w.category == flt.category)
            and (flt.tag is None or flt.tag in w.tags)
            and (flt.author_id is None or w.author.id == flt.author_id)
        ]
        rows.sort(key=lambda w: w.id)
        rows.sort(key=lambda w: _sort_value(w, page.sort_field), reverse=page.direction == "desc")
        start = page.page * page.size
        return rows[start : start + page.size], len(rows)

    async def update_if_version(
        self,
        wallpaper_id: str,
        expected_version: int,
        changes: Mapping[str, object],
        now: datetime,
    ) -> Wallpaper | None:
        current = self.items.get(wallpaper_id)
        if self.fail_next_update:
            self.fail_next_update = False
            return None
        if current is None or current.version != expected_version:
            return None
        values: dict[str, object] = {**changes, "updated_at": now, "version": current.version + 1}
        if "category" in values:
            values["category"] = Category(str(values["category"]))
        updated = replace(current, **values)  # pyright: ignore[reportArgumentType]
        self.items[wallpaper_id] = updated
        return updated


@pytest.fixture
def store() -> InMemoryWallpaperStore:
    return InMemoryWallpaperStore()


@pytest.fixture
def app(store: InMemoryWallpaperStore) -> FastAPI:
    app = create_app(Settings())  # pyright: ignore[reportCallIssue]
    ids = iter(f"wp_TEST{n:08d}" for n in range(1, 1000))
    tick = iter(datetime(2026, 10, 22, 8, 0, s, tzinfo=UTC) for s in range(0, 60))
    service = WallpaperService(
        store=store,
        authors=LocalAuthorDirectory(),
        clock=lambda: next(tick),
        new_id=lambda: next(ids),
    )
    app.dependency_overrides[get_wallpaper_service] = lambda: service
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def valid_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "title": "Misty Pines",
        "description": "Fog over a pine forest at dawn",
        "tags": ["forest", "fog"],
        "category": "NATURE",
        "assetId": "ast_01HXABCDEFGH",
        "authorId": "user-1234567890",
    }
    body.update(overrides)
    return body
