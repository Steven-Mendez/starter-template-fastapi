"""SQLModel table definition for Kanban columns."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class ColumnTable(SQLModel, table=True):
    """Persistence row for a Kanban column belonging to a single board.

    Reordering columns inside a single transaction can briefly produce
    duplicate ``position`` values, which is why the unique constraint
    is deferred until commit.
    """

    __tablename__ = "columns_"
    # Reordering columns can temporarily duplicate positions inside a transaction.
    # Deferring the unique check validates only the final committed order.
    __table_args__ = (
        sa.UniqueConstraint(
            "board_id",
            "position",
            name="uq_columns_board_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.CheckConstraint("position >= 0", name="ck_columns_position_non_negative"),
    )

    id: str = Field(primary_key=True)
    board_id: str = Field(foreign_key="boards.id", index=True, ondelete="CASCADE")
    title: str
    position: int
    created_by: UUID | None = Field(default=None, nullable=True)
    updated_by: UUID | None = Field(default=None, nullable=True)
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    deletion_id: UUID | None = Field(default=None, nullable=True)
