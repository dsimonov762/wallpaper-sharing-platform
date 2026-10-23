"""create media tables

Revision ID: 0001
Revises:
Create Date: 2026-10-22 10:59:58.653607
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_asset",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="PROCESSING", nullable=False),
        sa.Column("original_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("phash", sa.String(length=64), nullable=True),
        sa.Column("blurhash", sa.String(length=100), nullable=True),
        sa.Column("palette", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('AVATAR', 'BANNER', 'WALLPAPER')", name=op.f("ck_media_asset_purpose")
        ),
        sa.CheckConstraint(
            "status IN ('PROCESSING', 'READY', 'REJECTED')", name=op.f("ck_media_asset_status")
        ),
        sa.CheckConstraint(
            "height IS NULL OR height > 0", name=op.f("ck_media_asset_height_positive")
        ),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_media_asset_size_bytes_positive")),
        sa.CheckConstraint(
            "width IS NULL OR width > 0", name=op.f("ck_media_asset_width_positive")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_asset")),
        sa.UniqueConstraint("original_key", name=op.f("uq_media_asset_original_key")),
    )
    op.create_index(
        "ix_media_asset_owner_id_created_at",
        "media_asset",
        ["owner_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "media_variant",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_media_variant_size_bytes_positive")),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name=op.f("ck_media_variant_dimensions_positive")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["media_asset.id"],
            name=op.f("fk_media_variant_asset_id_media_asset"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_variant")),
        sa.UniqueConstraint("asset_id", "kind", name="uq_media_variant_asset_id_kind"),
        sa.UniqueConstraint("key", name=op.f("uq_media_variant_key")),
    )


def downgrade() -> None:
    op.drop_table("media_variant")
    op.drop_index("ix_media_asset_owner_id_created_at", table_name="media_asset")
    op.drop_table("media_asset")
