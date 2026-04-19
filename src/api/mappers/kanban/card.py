from __future__ import annotations

from datetime import datetime
from typing import TypedDict, cast

from src.api.schemas.kanban import CardCreate, CardRead, CardUpdate
from src.domain.kanban.models import Card, CardPriority


class PatchCardInput(TypedDict):
    title: str | None
    description: str | None
    column_id: str | None
    position: int | None
    priority: CardPriority | None
    due_at: datetime | None
    has_due_at: bool


def to_create_card_input(
    body: CardCreate,
) -> tuple[str, str | None, CardPriority, datetime | None]:
    return (body.title, body.description, body.priority, body.due_at)


def to_patch_card_input(body: CardUpdate) -> PatchCardInput:
    updates = body.model_dump(exclude_unset=True)
    return {
        "title": updates.get("title"),
        "description": updates.get("description"),
        "column_id": str(updates["column_id"]) if "column_id" in updates else None,
        "position": updates.get("position"),
        "priority": updates.get("priority"),
        "due_at": cast(datetime | None, updates.get("due_at")),
        "has_due_at": "due_at" in updates,
    }


def has_patch_card_changes(input_data: PatchCardInput) -> bool:
    if input_data["has_due_at"]:
        return True

    return any(
        value is not None
        for value in (
            input_data["title"],
            input_data["description"],
            input_data["column_id"],
            input_data["position"],
            input_data["priority"],
        )
    )


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
