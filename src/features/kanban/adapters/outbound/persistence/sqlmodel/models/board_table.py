"""SQLModel table definition for Kanban boards."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class BoardTable(SQLModel, table=True):
    """Persistence row for the Kanban :class:`Board` aggregate root.

    ``version`` is incremented on every write and used as an optimistic
    lock so two concurrent saves of the same aggregate do not overwrite
    each other silently.
    """

    __tablename__ = "boards"
    __table_args__ = (
        sa.Index(
            "ix_boards_active",
            "id",
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )

    id: str = Field(primary_key=True)
    title: str
    version: int = Field(default=1, sa_column=sa.Column(sa.Integer(), nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    # Plain UUID columns without FK to auth.users — kanban must not depend
    # on the auth schema, so referential integrity is sacrificed for
    # cross-feature isolation.
    created_by: UUID | None = Field(default=None, nullable=True)
    updated_by: UUID | None = Field(default=None, nullable=True)
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    # ``deletion_id`` ties a soft-delete cascade together so ``restore``
    # can revert the exact set of rows that were deleted in one operation.
    deletion_id: UUID | None = Field(default=None, nullable=True)
