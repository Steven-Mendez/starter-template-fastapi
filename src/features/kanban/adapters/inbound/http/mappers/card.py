"""Transport-to-application mappers for card payloads.

The patch mapper is more involved than its peers because the HTTP API
needs to distinguish a "due_at omitted" patch (leave the existing date
alone) from a "due_at set to null" patch (clear the date).
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict, cast

from src.features.kanban.adapters.inbound.http.schemas import (
    CardCreate,
    CardPrioritySchema,
    CardRead,
    CardUpdate,
)
from src.features.kanban.application.contracts import AppCard, AppCardPriority


class PatchCardInput(TypedDict):
    """Strongly-typed shape consumed by :class:`PatchCardCommand`."""

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
    """Map a :class:`CardCreate` body to the create-card use case inputs."""
    return (
        body.title,
        body.description,
        AppCardPriority(body.priority.value),
        body.due_at,
    )


def to_patch_card_input(body: CardUpdate) -> PatchCardInput:
    """Translate a :class:`CardUpdate` into the structured input the use case expects.

    Uses ``model_dump(exclude_unset=True)`` so the mapper can tell apart
    "field omitted" from "field explicitly set to ``None``", which is the
    cue that the caller wants to clear ``due_at`` rather than leave it.
    """
    # exclude_unset preserves the API contract: omitted fields mean unchanged,
    # while an explicit JSON null for due_at means clear the due date.
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


def to_card_response(value: AppCard) -> CardRead:
    """Project an :class:`AppCard` into the public :class:`CardRead` HTTP shape."""
    return CardRead(
        id=value.id,
        column_id=value.column_id,
        title=value.title,
        description=value.description,
        position=value.position,
        priority=CardPrioritySchema(value.priority.value),
        due_at=value.due_at,
    )
