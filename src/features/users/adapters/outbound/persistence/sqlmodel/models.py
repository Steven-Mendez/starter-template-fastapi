"""SQLModel table definitions owned by the users feature."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)


class UserTable(SQLModel, table=True):
    """User account row.

    Holds activity flags and the ``authz_version`` counter used to
    invalidate already-issued JWTs whenever a user's relationships
    change. Password credentials live in the authentication feature's
    ``credentials`` table.
    """

    __tablename__ = "users"
    __table_args__ = (
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.CheckConstraint(
            "authz_version >= 1", name="ck_users_authz_version_positive"
        ),
        # Composite index supports keyset pagination on the admin user-list
        # endpoint: ``WHERE (created_at, id) > (:c, :i) ORDER BY created_at, id``.
        # Declared here for ``--autogenerate`` consistency; the production
        # rollout uses ``CREATE INDEX CONCURRENTLY`` (see
        # ``alembic/migration_helpers.py``) so the build does not lock writes.
        sa.Index("ix_users_created_at", "created_at", "id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    is_verified: bool = Field(default=False, nullable=False)
    is_erased: bool = Field(default=False, nullable=False)
    authz_version: int = Field(default=1, nullable=False)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    last_login_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )


__all__ = ["UserTable", "utc_now"]
