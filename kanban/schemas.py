from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BoardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class BoardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)


class BoardSummary(BaseModel):
    id: str
    title: str
    created_at: datetime


class CardRead(BaseModel):
    id: str
    column_id: str
    title: str
    description: str | None
    position: int


class ColumnRead(BaseModel):
    id: str
    board_id: str
    title: str
    position: int
    cards: list[CardRead] = Field(default_factory=list)


class BoardDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    columns: list[ColumnRead] = Field(default_factory=list)


class ColumnCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class CardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None


class CardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    column_id: str | None = None
    position: int | None = Field(default=None, ge=0)
