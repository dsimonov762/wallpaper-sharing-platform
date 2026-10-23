"""Database tables as Python classes (SQLAlchemy 2.0 typed ORM)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Integer, MetaData, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names (pk_users, uq_users_email, ...). Without this, Postgres
# invents names and later migrations can't refer to them reliably.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserEntity(Base):
    __tablename__ = "users"

    # No default: the id is always the identity provider's id (= Keycloak `sub`).
    id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(String(500))
    locale: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    avatar_asset_id: Mapped[UUID | None]
    banner_asset_id: Mapped[UUID | None]
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    version: Mapped[int] = mapped_column(Integer, server_default="1")

    __table_args__ = (CheckConstraint("status IN ('ACTIVE', 'SUSPENDED')", name="status_valid"),)
    # version_id_col = optimistic locking: every UPDATE adds 1 and fails if someone else
    # changed the row in between. eager_defaults = read server-generated values back
    # immediately (async code cannot lazy-load them later).
    __mapper_args__ = {"version_id_col": version, "eager_defaults": True}  # noqa: RUF012
