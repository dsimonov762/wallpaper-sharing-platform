import pytest

from catalog.repository.database import MongoDatabase
from catalog.repository.indexes import WALLPAPER_INDEXES, ensure_indexes

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_ensure_indexes_creates_all_and_is_idempotent(database: MongoDatabase) -> None:
    first = await ensure_indexes(database)
    second = await ensure_indexes(database)
    assert sorted(first) == sorted(second) == sorted(i.document["name"] for i in WALLPAPER_INDEXES)
    existing = {i["name"] async for i in await database.wallpapers.list_indexes()}
    assert existing == {"_id_", *first}


async def test_status_created_index_is_used_by_the_default_listing(database: MongoDatabase) -> None:
    await ensure_indexes(database)
    for n in range(50):
        await database.wallpapers.insert_one(
            {"_id": f"wp_{n}", "status": "PUBLISHED", "createdAt": n}
        )
    plan = await database.wallpapers.find({"status": "PUBLISHED"}).sort("createdAt", -1).explain()
    assert "IXSCAN" in str(plan["queryPlanner"]["winningPlan"])
