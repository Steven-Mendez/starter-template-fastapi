from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class BoardTable(SQLModel, table=True):
    __tablename__ = "boards"

    id: str = Field(primary_key=True)
    title: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class ColumnTable(SQLModel, table=True):
    __tablename__ = "columns_"

    id: str = Field(primary_key=True)
    board_id: str = Field(foreign_key="boards.id", index=True, ondelete="CASCADE")
    title: str
    position: int


class CardTable(SQLModel, table=True):
    __tablename__ = "cards"

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


def get_sqlmodel_metadata() -> sa.MetaData:
    return SQLModel.metadata
