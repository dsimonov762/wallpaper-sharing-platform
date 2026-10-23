"""MongoDB implementation of the WallpaperStore port."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.asynchronous.collection import AsyncCollection

from catalog.domain.models import Wallpaper
from catalog.domain.ports import PageRequest, WallpaperFilter
from catalog.repository.documents import from_document, to_document


def build_query(flt: WallpaperFilter) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if flt.status is not None:
        query["status"] = flt.status.value
    if flt.category is not None:
        query["category"] = flt.category.value
    if flt.tag is not None:
        query["tags"] = flt.tag  # matches when the array contains the value
    if flt.author_id is not None:
        query["author.id"] = flt.author_id
    return query


class MongoWallpaperRepository:
    def __init__(self, collection: AsyncCollection[dict[str, Any]]) -> None:
        self._collection = collection

    async def insert(self, wallpaper: Wallpaper) -> None:
        await self._collection.insert_one(to_document(wallpaper))

    async def get(self, wallpaper_id: str) -> Wallpaper | None:
        doc = await self._collection.find_one({"_id": wallpaper_id})
        return None if doc is None else from_document(doc)

    async def list(self, flt: WallpaperFilter, page: PageRequest) -> tuple[list[Wallpaper], int]:
        query = build_query(flt)
        total = await self._collection.count_documents(query)
        direction = ASCENDING if page.direction == "asc" else DESCENDING
        # "_id" is a tie-breaker: without it, equal sort values could shuffle between pages.
        cursor = (
            self._collection.find(query)
            .sort([(page.sort_field, direction), ("_id", ASCENDING)])
            .skip(page.page * page.size)
            .limit(page.size)
        )
        docs = await cursor.to_list(length=page.size)
        return [from_document(d) for d in docs], total

    async def update_if_version(
        self,
        wallpaper_id: str,
        expected_version: int,
        changes: Mapping[str, object],
        now: datetime,
    ) -> Wallpaper | None:
        # One atomic operation: the filter checks the version and $inc bumps it (no read-write gap).
        doc = await self._collection.find_one_and_update(
            {"_id": wallpaper_id, "version": expected_version},
            {"$set": {**changes, "updatedAt": now}, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )
        return None if doc is None else from_document(doc)
