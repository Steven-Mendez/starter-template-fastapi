"""SQLModel table definition for Kanban cards."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class CardTable(SQLModel, table=True):
    """Persistence row for a card belonging to a single column.

    Card priorities are stored as plain strings instead of an enum so
    new priority levels can be introduced without an Alembic migration
    that would otherwise need to alter a database-side type.
    """

    __tablename__ = "cards"
    # Reordering cards can temporarily duplicate positions inside a transaction.
    # Deferring the unique check validates only the final committed order.
    __table_args__ = (
        sa.UniqueConstraint(
            "column_id",
            "position",
            name="uq_cards_column_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.CheckConstraint("position >= 0", name="ck_cards_position_non_negative"),
        sa.Index(
            "ix_cards_active",
            "id",
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
    )

    id: str = Field(primary_key=True)
    column_id: str = Field(foreign_key="columns_.id", index=True, ondelete="CASCADE")
    title: str
    description: str | None = None
    position: int
    priority: str
    due_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    created_by: UUID | None = Field(default=None, nullable=True)
    updated_by: UUID | None = Field(default=None, nullable=True)
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    deletion_id: UUID | None = Field(default=None, nullable=True)
