from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from src.api.schemas.kanban import (
    BoardCreate,
    BoardDetail,
    BoardSummary,
    BoardUpdate,
    CardCreate,
    CardRead,
    CardUpdate,
    ColumnCreate,
    ColumnRead,
)
from src.domain.kanban.models import Board, Card, CardPriority, Column
from src.domain.kanban.models import BoardSummary as DomainBoardSummary


class PatchCardInput(TypedDict):
    title: str | None
    description: str | None
    column_id: str | None
    position: int | None
    priority: CardPriority | None
    due_at: object


def to_create_board_input(body: BoardCreate) -> str:
    return body.title


def to_patch_board_input(body: BoardUpdate) -> str | None:
    return body.title


def to_create_column_input(body: ColumnCreate) -> str:
    return body.title


def to_create_card_input(
    body: CardCreate,
) -> tuple[str, str | None, CardPriority, datetime | None]:
    return (body.title, body.description, body.priority, body.due_at)


def to_patch_card_input(body: CardUpdate, due_at_unset: object) -> PatchCardInput:
    updates = body.model_dump(exclude_unset=True)
    return {
        "title": updates.get("title"),
        "description": updates.get("description"),
        "column_id": str(updates["column_id"]) if "column_id" in updates else None,
        "position": updates.get("position"),
        "priority": updates.get("priority"),
        "due_at": updates["due_at"] if "due_at" in updates else due_at_unset,
    }


def to_board_summary_response(value: DomainBoardSummary) -> BoardSummary:
    return BoardSummary(id=value.id, title=value.title, created_at=value.created_at)


def to_card_response(value: Card) -> CardRead:
    return CardRead(
        id=value.id,
        column_id=value.column_id,
        title=value.title,
        description=value.description,
        position=value.position,
        priority=value.priority,
        due_at=value.due_at,
    )


def to_column_response(value: Column) -> ColumnRead:
    return ColumnRead(
        id=value.id,
        board_id=value.board_id,
        title=value.title,
        position=value.position,
        cards=[to_card_response(card) for card in value.cards],
    )


def to_board_detail_response(value: Board) -> BoardDetail:
    return BoardDetail(
        id=value.id,
        title=value.title,
        created_at=value.created_at,
        columns=[to_column_response(column) for column in value.columns],
    )
