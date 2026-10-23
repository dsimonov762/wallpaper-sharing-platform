"""Translation between the domain model and the MongoDB document (README 6.3 field names)."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from catalog.domain.models import (
    Author,
    Category,
    Dimensions,
    Variant,
    Wallpaper,
    WallpaperStatus,
)


def _utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def to_document(w: Wallpaper) -> dict[str, Any]:
    return {
        "_id": w.id,
        "title": w.title,
        "description": w.description,
        "tags": list(w.tags),
        "category": w.category.value,
        "status": w.status.value,
        "assetId": w.asset_id,
        "variants": [
            {"kind": v.kind, "url": v.url, "width": v.width, "height": v.height} for v in w.variants
        ],
        "dimensions": (
            None
            if w.dimensions is None
            else {"width": w.dimensions.width, "height": w.dimensions.height}
        ),
        "palette": list(w.palette),
        "blurhash": w.blurhash,
        "author": {
            "id": w.author.id,
            "username": w.author.username,
            "displayName": w.author.display_name,
            "avatarUrl": w.author.avatar_url,
        },
        "favoriteCount": w.favorite_count,
        "createdAt": w.created_at,
        "updatedAt": w.updated_at,
        "version": w.version,
    }


def from_document(doc: Mapping[str, Any]) -> Wallpaper:
    author = doc["author"]
    dims = doc.get("dimensions")
    return Wallpaper(
        id=doc["_id"],
        title=doc["title"],
        description=doc["description"],
        tags=list(doc["tags"]),
        category=Category(doc["category"]),
        status=WallpaperStatus(doc["status"]),
        asset_id=doc["assetId"],
        variants=[
            Variant(kind=v["kind"], url=v["url"], width=v["width"], height=v["height"])
            for v in doc.get("variants", [])
        ],
        dimensions=None if dims is None else Dimensions(width=dims["width"], height=dims["height"]),
        palette=list(doc.get("palette", [])),
        blurhash=doc.get("blurhash"),
        author=Author(
            id=author["id"],
            username=author["username"],
            display_name=author["displayName"],
            avatar_url=author.get("avatarUrl"),
        ),
        favorite_count=doc.get("favoriteCount", 0),
        created_at=_utc(doc["createdAt"]),
        updated_at=_utc(doc["updatedAt"]),
        version=doc["version"],
    )
