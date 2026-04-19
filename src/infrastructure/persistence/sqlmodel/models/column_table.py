from __future__ import annotations

from sqlmodel import Field, SQLModel


class ColumnTable(SQLModel, table=True):
    __tablename__ = "columns_"

    id: str = Field(primary_key=True)
    board_id: str = Field(foreign_key="boards.id", index=True, ondelete="CASCADE")
    title: str
    position: int
