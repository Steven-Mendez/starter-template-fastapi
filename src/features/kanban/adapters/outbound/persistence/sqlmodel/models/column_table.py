from __future__ import annotations

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class ColumnTable(SQLModel, table=True):
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
