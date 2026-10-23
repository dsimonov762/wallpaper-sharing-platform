"""Integration setup: a real MongoDB, a throwaway database name, a clean collection per test.

Run with: just catalog-test-integration  (needs `just infra-up` and a .env next to pyproject).
"""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from catalog.config.settings import Settings
from catalog.domain.models import (
    Author,
    Category,
    Wallpaper,
    WallpaperStatus,
)
from catalog.repository.database import MongoDatabase, create_mongo_database
from catalog.repository.wallpaper_repository import MongoWallpaperRepository

TEST_DATABASE = "catalog_test"


@pytest.fixture(scope="session")
def settings() -> Settings:
    loaded = Settings(mongodb_database=TEST_DATABASE, environment="test")  # pyright: ignore[reportCallIssue]
    if "unit-test.invalid" in loaded.mongodb_uri.get_secret_value():
        pytest.exit("Run integration tests on their own: pytest tests/integration -m integration")
    return loaded


@pytest.fixture(scope="session", autouse=True)
def _require_mongodb(settings: Settings) -> Iterator[None]:
    client: MongoClient[dict[str, object]] = MongoClient(
        settings.mongodb_uri.get_secret_value(), serverSelectionTimeoutMS=2000
    )
    try:
        client.admin.command("ping")
    except OperationFailure as exc:
        pytest.exit(f"MongoDB rejected the credentials in CATALOG_MONGODB_URI: {exc}")
    except PyMongoError as exc:
        pytest.exit(f"MongoDB is not reachable ({exc.__class__.__name__}). Run: just infra-up")
    yield
    client.close()


@pytest.fixture(autouse=True)
def clean_collection(settings: Settings) -> Iterator[None]:
    """Each test starts and ends with an empty wallpapers collection in catalog_test."""
    client: MongoClient[dict[str, object]] = MongoClient(settings.mongodb_uri.get_secret_value())
    collection = client[TEST_DATABASE]["wallpapers"]
    collection.drop()
    yield
    collection.drop()
    client.close()


@pytest_asyncio.fixture
async def database(settings: Settings) -> AsyncIterator[MongoDatabase]:
    db = create_mongo_database(settings)
    yield db
    await db.close()


@pytest.fixture
def repository(database: MongoDatabase) -> MongoWallpaperRepository:
    return MongoWallpaperRepository(database.wallpapers)


def make_wallpaper(
    n: int,
    *,
    title: str | None = None,
    category: Category = Category.NATURE,
    tags: list[str] | None = None,
    author_id: str = "u-alice",
    created_second: int | None = None,
) -> Wallpaper:
    created = datetime(
        2026, 10, 22, 8, 0, created_second if created_second is not None else n, tzinfo=UTC
    )
    return Wallpaper(
        id=f"wp_IT{n:010d}",
        title=title or f"Wallpaper {n}",
        description="",
        tags=tags or ["forest"],
        category=category,
        status=WallpaperStatus.PENDING_MEDIA,
        asset_id="ast_01HXABCDEFGH",
        author=Author(id=author_id, username="alice", display_name="Alice", avatar_url=None),
        created_at=created,
        updated_at=created,
        version=1,
    )
