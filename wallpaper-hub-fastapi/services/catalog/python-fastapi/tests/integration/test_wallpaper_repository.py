"""The Mongo repository against a real MongoDB."""

import asyncio
from datetime import UTC, datetime

import pytest

from catalog.domain.models import Category, WallpaperStatus
from catalog.domain.ports import PageRequest, WallpaperFilter
from catalog.repository.wallpaper_repository import MongoWallpaperRepository
from tests.integration.conftest import make_wallpaper

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

NEWEST_FIRST = PageRequest(page=0, size=20, sort_field="createdAt", direction="desc")


async def test_insert_and_get_round_trip(repository: MongoWallpaperRepository) -> None:
    original = make_wallpaper(1)
    await repository.insert(original)
    assert await repository.get(original.id) == original


async def test_get_missing_returns_none(repository: MongoWallpaperRepository) -> None:
    assert await repository.get("wp_NOPE") is None


async def test_update_if_version_applies_changes_and_bumps_version(
    repository: MongoWallpaperRepository,
) -> None:
    await repository.insert(make_wallpaper(1))
    now = datetime(2026, 10, 22, 9, 0, 0, tzinfo=UTC)
    updated = await repository.update_if_version(
        "wp_IT0000000001", 1, {"title": "Renamed", "category": "CITY"}, now
    )
    assert updated is not None
    assert (updated.title, updated.category, updated.version) == ("Renamed", Category.CITY, 2)
    assert updated.updated_at == now
    assert updated.created_at == make_wallpaper(1).created_at
    assert updated.author == make_wallpaper(1).author  # untouched fields stay untouched


async def test_update_with_stale_version_changes_nothing(
    repository: MongoWallpaperRepository,
) -> None:
    await repository.insert(make_wallpaper(1))
    now = datetime(2026, 10, 22, 9, 0, 0, tzinfo=UTC)
    assert await repository.update_if_version("wp_IT0000000001", 7, {"title": "x"}, now) is None
    stored = await repository.get("wp_IT0000000001")
    assert stored is not None
    assert (stored.title, stored.version) == ("Wallpaper 1", 1)


async def test_update_missing_document_returns_none(repository: MongoWallpaperRepository) -> None:
    now = datetime(2026, 10, 22, 9, 0, 0, tzinfo=UTC)
    assert await repository.update_if_version("wp_NOPE", 1, {"title": "x"}, now) is None


async def test_two_writers_with_the_same_version_exactly_one_wins(
    repository: MongoWallpaperRepository,
) -> None:
    """The lost-update problem: both read version 1, both try to save."""
    await repository.insert(make_wallpaper(1))
    now = datetime(2026, 10, 22, 9, 0, 0, tzinfo=UTC)
    results = await asyncio.gather(
        *(
            repository.update_if_version("wp_IT0000000001", 1, {"title": f"w{i}"}, now)
            for i in range(8)
        )
    )
    winners = [r for r in results if r is not None]
    assert len(winners) == 1
    stored = await repository.get("wp_IT0000000001")
    assert stored is not None
    assert stored.version == 2


async def test_list_filters_on_status_category_tag_and_author(
    repository: MongoWallpaperRepository,
) -> None:
    await repository.insert(make_wallpaper(1, category=Category.NATURE, tags=["forest", "fog"]))
    await repository.insert(
        make_wallpaper(2, category=Category.CITY, tags=["night"], author_id="u-bob")
    )
    await repository.insert(make_wallpaper(3, category=Category.NATURE, tags=["fog"]))

    async def ids(flt: WallpaperFilter) -> list[str]:
        items, _ = await repository.list(flt, NEWEST_FIRST)
        return [w.id[-1] for w in items]

    assert await ids(WallpaperFilter()) == ["3", "2", "1"]
    assert await ids(WallpaperFilter(category=Category.NATURE)) == ["3", "1"]
    assert await ids(WallpaperFilter(tag="fog")) == ["3", "1"]  # matches inside the tags array
    assert await ids(WallpaperFilter(author_id="u-bob")) == ["2"]  # matches the nested author.id
    assert await ids(WallpaperFilter(status=WallpaperStatus.PUBLISHED)) == []


async def test_list_pages_and_total(repository: MongoWallpaperRepository) -> None:
    for n in range(1, 6):
        await repository.insert(make_wallpaper(n))
    page = PageRequest(page=1, size=2, sort_field="createdAt", direction="desc")
    items, total = await repository.list(WallpaperFilter(), page)
    assert total == 5
    assert [w.id[-1] for w in items] == ["3", "2"]


async def test_equal_sort_values_keep_a_stable_order_across_pages(
    repository: MongoWallpaperRepository,
) -> None:
    """Same createdAt for every row: the _id tie-breaker must prevent duplicates or gaps."""
    for n in range(1, 8):
        await repository.insert(make_wallpaper(n, created_second=0))
    seen: list[str] = []
    for page_number in range(4):
        page = PageRequest(page=page_number, size=2, sort_field="createdAt", direction="desc")
        items, _ = await repository.list(WallpaperFilter(), page)
        seen += [w.id for w in items]
    assert len(seen) == 7
    assert len(set(seen)) == 7


async def test_list_sorts_by_title_both_ways(repository: MongoWallpaperRepository) -> None:
    for n, title in enumerate(["Bravo", "Alpha", "Charlie"], start=1):
        await repository.insert(make_wallpaper(n, title=title))
    asc = PageRequest(page=0, size=10, sort_field="title", direction="asc")
    desc = PageRequest(page=0, size=10, sort_field="title", direction="desc")
    assert [w.title for w in (await repository.list(WallpaperFilter(), asc))[0]] == [
        "Alpha",
        "Bravo",
        "Charlie",
    ]
    assert [w.title for w in (await repository.list(WallpaperFilter(), desc))[0]] == [
        "Charlie",
        "Bravo",
        "Alpha",
    ]
