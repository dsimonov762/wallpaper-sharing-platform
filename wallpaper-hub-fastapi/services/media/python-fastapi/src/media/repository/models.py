"""Database tables `media_asset` and `media_variant` (README section 6.2)."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from media.domain.models import MediaPurpose, MediaStatus

# Every constraint gets a predictable name, so migrations can drop or change it later and error
# messages say which rule was broken (for example `uq_media_asset_original_key`).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def _one_of(column: str, values: type[StrEnum]) -> str:
    """SQL text for a CHECK constraint: the column must hold one of the enum's values."""
    allowed = ", ".join(f"'{member.value}'" for member in values)
    return f"{column} IN ({allowed})"


class TimestampMixin:
    """`created_at` and `updated_at`, both filled in by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MediaAsset(TimestampMixin, Base):
    """One uploaded file (the private original) and everything we learn about it."""

    __tablename__ = "media_asset"

    # uuid7 (new in Python 3.14) is time-ordered, which keeps the primary-key index compact.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)  # Keycloak `sub`
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=MediaStatus.PROCESSING.value,
        server_default=MediaStatus.PROCESSING.value,
    )
    original_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Filled in by the image pipeline, so they are empty while the asset is PROCESSING.
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    phash: Mapped[str | None] = mapped_column(String(64))
    blurhash: Mapped[str | None] = mapped_column(String(100))
    palette: Mapped[list[str] | None] = mapped_column(JSONB)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    variants: Mapped[list["MediaVariant"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        passive_deletes=True,  # the database cascades the delete (ON DELETE CASCADE)
        lazy="raise",  # async code cannot lazy-load: ask for variants explicitly
    )

    __table_args__ = (
        CheckConstraint(_one_of("purpose", MediaPurpose), name="purpose"),
        CheckConstraint(_one_of("status", MediaStatus), name="status"),
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        CheckConstraint("width IS NULL OR width > 0", name="width_positive"),
        CheckConstraint("height IS NULL OR height > 0", name="height_positive"),
        UniqueConstraint("original_key"),
        Index("ix_media_asset_owner_id_created_at", "owner_id", "created_at"),
    )
    __mapper_args__ = {  # noqa: RUF012  (SQLAlchemy reads this plain class attribute)
        "version_id_col": version,  # optimistic locking: a stale save raises StaleDataError
        "eager_defaults": True,  # read back updated_at after UPDATE (async cannot lazy-load it)
    }


class MediaVariant(TimestampMixin, Base):
    """One generated rendition of an asset (thumbnail, preview, ...), stored in S3."""

    __tablename__ = "media_variant"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid7)
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("media_asset.id", ondelete="CASCADE"), nullable=False
    )
    # No CHECK on `kind` yet: the full list of variants per purpose is decided together with the
    # image pipeline, and that slice adds the constraint.
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)  # object key in S3
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    asset: Mapped[MediaAsset] = relationship(back_populates="variants", lazy="raise")

    __table_args__ = (
        CheckConstraint("width > 0 AND height > 0", name="dimensions_positive"),
        CheckConstraint("size_bytes > 0", name="size_bytes_positive"),
        UniqueConstraint("asset_id", "kind", name="uq_media_variant_asset_id_kind"),
        UniqueConstraint("key"),
    )
    __mapper_args__ = {  # noqa: RUF012
        "version_id_col": version,
        "eager_defaults": True,
    }
