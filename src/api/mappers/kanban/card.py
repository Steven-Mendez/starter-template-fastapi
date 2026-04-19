from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from src.api.schemas.kanban import CardCreate, CardRead, CardUpdate
from src.domain.kanban.models import Card, CardPriority


class PatchCardInput(TypedDict):
    title: str | None
    description: str | None
    column_id: str | None
    position: int | None
    priority: CardPriority | None
    due_at: object


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
