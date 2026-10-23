"""align users with readme

Adds the profile/soft-delete/versioning columns from README section 6.1 and replaces the
placeholder `avatar_url` with `avatar_asset_id`.

Revision ID: 6111221a9242
Revises: cb82e37f8407
Create Date: 2026-10-13 10:30:33.125002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6111221a9242"
down_revision: str | None = "cb82e37f8407"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.String(length=500), nullable=True))
    op.add_column("users", sa.Column("avatar_asset_id", sa.Uuid(), nullable=True))
    op.add_column("users", sa.Column("banner_asset_id", sa.Uuid(), nullable=True))
    op.add_column(
        "users", sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False)
    )
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.drop_column("users", "avatar_url")
    # Autogenerate does not detect CHECK constraints, so this one is written by hand.
    op.create_check_constraint(
        op.f("ck_users_status_valid"), "users", "status IN ('ACTIVE', 'SUSPENDED')"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_users_status_valid"), "users", type_="check")
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(length=2048), nullable=True),
    )
    op.drop_column("users", "version")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "status")
    op.drop_column("users", "banner_asset_id")
    op.drop_column("users", "avatar_asset_id")
    op.drop_column("users", "bio")
