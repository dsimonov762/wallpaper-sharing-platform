"""The Mongo document keeps README 6.3 field names and survives a round trip."""

from datetime import UTC, datetime

from catalog.domain.models import (
    Author,
    Category,
    Dimensions,
    Variant,
    Wallpaper,
    WallpaperStatus,
)
from catalog.repository.documents import from_document, to_document


def sample() -> Wallpaper:
    return Wallpaper(
        id="wp_TEST00000001",
        title="Misty Pines",
        description="Fog",
        tags=["forest", "fog"],
        category=Category.NATURE,
        status=WallpaperStatus.PENDING_MEDIA,
        asset_id="ast_01HXABCDEFGH",
        author=Author(id="u1", username="alice", display_name="Alice", avatar_url=None),
        created_at=datetime(2026, 10, 22, 8, 0, tzinfo=UTC),
        updated_at=datetime(2026, 10, 22, 8, 5, tzinfo=UTC),
        version=3,
        favorite_count=12,
        variants=[Variant(kind="THUMBNAIL", url="u", width=320, height=180)],
        dimensions=Dimensions(width=3840, height=2160),
        palette=["#2b3a2f"],
        blurhash="LKO2",
    )


def test_document_uses_readme_field_names() -> None:
    doc = to_document(sample())
    assert doc["_id"] == "wp_TEST00000001"
    assert doc["assetId"] == "ast_01HXABCDEFGH"
    assert doc["favoriteCount"] == 12
    assert doc["author"]["displayName"] == "Alice"
    assert doc["status"] == "PENDING_MEDIA"


def test_round_trip_keeps_everything() -> None:
    assert from_document(to_document(sample())) == sample()


def test_naive_datetimes_from_mongo_are_read_as_utc() -> None:
    doc = to_document(sample())
    doc["createdAt"] = doc["createdAt"].replace(tzinfo=None)
    assert from_document(doc).created_at.tzinfo is UTC
