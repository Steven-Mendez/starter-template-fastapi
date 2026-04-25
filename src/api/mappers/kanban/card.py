from __future__ import annotations

from datetime import datetime
from typing import TypedDict, cast

from src.api.schemas.kanban import CardCreate, CardPrioritySchema, CardRead, CardUpdate
from src.application.contracts import AppCard, AppCardPriority


class PatchCardInput(TypedDict):
    title: str | None
    description: str | None
    column_id: str | None
    position: int | None
    priority: AppCardPriority | None
    due_at: datetime | None
    clear_due_at: bool


def to_create_card_input(
    body: CardCreate,
) -> tuple[str, str | None, AppCardPriority, datetime | None]:
    return (
        body.title,
        body.description,
        AppCardPriority(body.priority.value),
        body.due_at,
    )


def to_patch_card_input(body: CardUpdate) -> PatchCardInput:
    updates = body.model_dump(exclude_unset=True)
    wire_priority = cast(CardPrioritySchema | None, updates.get("priority"))
    return {
        "title": updates.get("title"),
        "description": updates.get("description"),
        "column_id": str(updates["column_id"]) if "column_id" in updates else None,
        "position": updates.get("position"),
        "priority": (
            AppCardPriority(wire_priority.value) if wire_priority is not None else None
        ),
        "due_at": cast(datetime | None, updates.get("due_at")),
        "clear_due_at": "due_at" in updates and updates.get("due_at") is None,
    }


def has_patch_card_changes(input_data: PatchCardInput) -> bool:
    if input_data["clear_due_at"]:
        return True

    return any(
        value is not None
        for value in (
            input_data["title"],
            input_data["description"],
            input_data["column_id"],
            input_data["position"],
            input_data["priority"],
            input_data["due_at"],
        )
    )


def to_card_response(value: AppCard) -> CardRead:
    return CardRead(
        id=value.id,
        column_id=value.column_id,
        title=value.title,
        description=value.description,
        position=value.position,
        priority=CardPrioritySchema(value.priority.value),
        due_at=value.due_at,
    )
