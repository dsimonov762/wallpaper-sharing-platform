"""Talks to the real database. Needs `just infra-up` and `just media-migrate` first."""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from media.repository.database import database_is_reachable
from media.repository.models import MediaAsset, MediaVariant

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _asset(**overrides: object) -> MediaAsset:
    values: dict[str, object] = {
        "owner_id": uuid.uuid7(),
        "purpose": "WALLPAPER",
        "original_key": f"originals/{uuid.uuid4()}.jpg",
        "content_type": "image/jpeg",
        "size_bytes": 1234,
    }
    values.update(overrides)
    return MediaAsset(**values)


def _variant(asset_id: uuid.UUID, kind: str = "THUMBNAIL") -> MediaVariant:
    return MediaVariant(
        asset_id=asset_id,
        kind=kind,
        key=f"variants/{uuid.uuid4()}.webp",
        width=320,
        height=180,
        format="webp",
        size_bytes=900,
    )


async def _save(session: AsyncSession, *rows: MediaAsset | MediaVariant) -> None:
    """Add rows and send the SQL now, inside a savepoint.

    If the database rejects a row, only the savepoint is undone, so the test can keep using
    the session. This is also what lets `pytest.raises` wrap a single statement.
    """
    async with session.begin_nested():
        session.add_all(rows)
        await session.flush()


async def test_database_is_reachable(engine: AsyncEngine) -> None:
    assert await database_is_reachable(engine) is True


async def test_migration_created_both_tables(session: AsyncSession) -> None:
    result = await session.execute(
        text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name LIKE 'media_%'"
        )
    )

    assert {row[0] for row in result} == {"media_asset", "media_variant"}


async def test_new_asset_gets_database_defaults(session: AsyncSession) -> None:
    asset = _asset()

    await _save(session, asset)

    assert asset.status == "PROCESSING"
    assert asset.version == 1
    assert asset.created_at is not None
    assert asset.width is None  # filled in later by the image pipeline


async def test_saving_a_change_bumps_the_version(session: AsyncSession) -> None:
    asset = _asset()
    await _save(session, asset)

    asset.status = "READY"
    await session.flush()

    assert asset.version == 2
    assert asset.updated_at >= asset.created_at


async def test_unknown_status_is_rejected_by_the_database(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_media_asset_status"):
        await _save(session, _asset(status="DONE"))


async def test_unknown_purpose_is_rejected_by_the_database(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_media_asset_purpose"):
        await _save(session, _asset(purpose="POSTER"))


async def test_original_key_must_be_unique(session: AsyncSession) -> None:
    await _save(session, _asset(original_key="originals/same.jpg"))

    with pytest.raises(IntegrityError, match="uq_media_asset_original_key"):
        await _save(session, _asset(original_key="originals/same.jpg"))


async def test_an_asset_has_at_most_one_variant_of_each_kind(session: AsyncSession) -> None:
    asset = _asset()
    await _save(session, asset)
    await _save(session, _variant(asset.id, "THUMBNAIL"))

    with pytest.raises(IntegrityError, match="uq_media_variant_asset_id_kind"):
        await _save(session, _variant(asset.id, "THUMBNAIL"))


async def test_a_variant_needs_an_existing_asset(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="fk_media_variant_asset_id_media_asset"):
        await _save(session, _variant(uuid.uuid7()))


async def test_deleting_an_asset_deletes_its_variants(session: AsyncSession) -> None:
    asset = _asset()
    await _save(session, asset)
    await _save(session, _variant(asset.id, "PREVIEW"))

    await session.execute(text("DELETE FROM media_asset WHERE id = :id"), {"id": asset.id})

    remaining = await session.scalars(select(MediaVariant).where(MediaVariant.asset_id == asset.id))
    assert remaining.all() == []
