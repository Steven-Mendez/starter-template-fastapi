"""SQLModel table definition for Kanban boards."""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlmodel import Field, SQLModel


class BoardTable(SQLModel, table=True):
    __tablename__ = "boards"

    id: str = Field(primary_key=True)
    title: str
    version: int = Field(default=1, sa_column=sa.Column(sa.Integer(), nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
