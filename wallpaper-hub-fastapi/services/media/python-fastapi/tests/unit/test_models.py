"""Pins the tables to README section 6.2, so a drive-by edit cannot silently change the schema."""

from sqlalchemy import CheckConstraint, Table, UniqueConstraint

from media.domain.models import MediaPurpose, MediaStatus
from media.repository.models import Base, MediaAsset, MediaVariant


def _table(model: type[Base]) -> Table:
    return Base.metadata.tables[str(model.__tablename__)]


def _columns(model: type[Base]) -> set[str]:
    return {column.name for column in _table(model).columns}


def _check_constraints(model: type[Base]) -> dict[str, str]:
    """Constraint name -> its SQL condition."""
    return {
        str(constraint.name): str(constraint.sqltext)
        for constraint in _table(model).constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_media_asset_has_the_readme_columns() -> None:
    assert _columns(MediaAsset) == {
        "id", "owner_id", "purpose", "status", "original_key", "content_type", "size_bytes",
        "width", "height", "sha256", "phash", "blurhash", "palette", "reject_reason",
        "created_at", "updated_at", "version",
    }  # fmt: skip


def test_media_variant_has_the_readme_columns() -> None:
    assert _columns(MediaVariant) == {
        "id", "asset_id", "kind", "key", "width", "height", "format", "size_bytes",
        "created_at", "updated_at", "version",
    }  # fmt: skip


def test_purpose_and_status_values_match_the_readme() -> None:
    assert {p.value for p in MediaPurpose} == {"AVATAR", "BANNER", "WALLPAPER"}
    assert {s.value for s in MediaStatus} == {"PROCESSING", "READY", "REJECTED"}


def test_check_constraints_are_generated_from_the_enums() -> None:
    checks = _check_constraints(MediaAsset)

    assert all(f"'{p.value}'" in checks["ck_media_asset_purpose"] for p in MediaPurpose)
    assert all(f"'{s.value}'" in checks["ck_media_asset_status"] for s in MediaStatus)


def test_constraints_have_predictable_names() -> None:
    assert set(_check_constraints(MediaAsset)) == {
        "ck_media_asset_purpose",
        "ck_media_asset_status",
        "ck_media_asset_size_bytes_positive",
        "ck_media_asset_width_positive",
        "ck_media_asset_height_positive",
    }
    unique = {
        str(constraint.name)
        for constraint in _table(MediaAsset).constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert unique == {"uq_media_asset_original_key"}
