"""Index definitions. Created by an explicit command, never at startup (like migrations)."""

from pymongo import ASCENDING, DESCENDING, IndexModel

from catalog.repository.database import MongoDatabase

WALLPAPER_INDEXES = [
    IndexModel(
        [("status", ASCENDING), ("createdAt", DESCENDING)], name="ix_wallpapers_status_created"
    ),
    IndexModel(
        [("category", ASCENDING), ("createdAt", DESCENDING)], name="ix_wallpapers_category_created"
    ),
    IndexModel(
        [("author.id", ASCENDING), ("createdAt", DESCENDING)], name="ix_wallpapers_author_created"
    ),
    IndexModel([("tags", ASCENDING)], name="ix_wallpapers_tags"),
]


async def ensure_indexes(database: MongoDatabase) -> list[str]:
    """Idempotent: creating an index that already exists with the same definition does nothing."""
    return await database.wallpapers.create_indexes(WALLPAPER_INDEXES)
