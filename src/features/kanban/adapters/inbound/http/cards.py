"""FastAPI routes for Kanban card resources."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from src.features.kanban.adapters.inbound.http.dependencies import (
    ActorIdDep,
    CreateCardUseCaseDep,
    GetCardUseCaseDep,
    PatchCardUseCaseDep,
)
from src.features.kanban.adapters.inbound.http.errors import (
    raise_http_from_application_error,
)
from src.features.kanban.adapters.inbound.http.mappers import (
    to_card_response,
    to_create_card_input,
    to_patch_card_input,
)
from src.features.kanban.adapters.inbound.http.schemas import (
    CardCreate,
    CardRead,
    CardUpdate,
)
from src.features.kanban.application.commands import (
    CreateCardCommand,
    PatchCardCommand,
)
from src.features.kanban.application.queries import GetCardQuery
from src.platform.shared.result import Err, Ok

cards_read_router = APIRouter(tags=["cards"])
cards_write_router = APIRouter(tags=["cards"])


@cards_write_router.post(
    "/columns/{column_id}/cards",
    status_code=status.HTTP_201_CREATED,
)
def create_card(
    column_id: UUID,
    body: CardCreate,
    use_case: CreateCardUseCaseDep,
    actor_id: ActorIdDep,
) -> CardRead:
    """Create a card inside the given column and return the persisted view."""
    title, description, priority, due_at = to_create_card_input(body)
    command = CreateCardCommand(
        column_id=str(column_id),
        title=title,
        description=description,
        priority=priority,
        due_at=due_at,
        actor_id=actor_id,
    )
    match use_case.execute(command):
        case Ok(value):
            return to_card_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@cards_read_router.get("/cards/{card_id}")
def get_card(card_id: UUID, use_case: GetCardUseCaseDep) -> CardRead:
    """Return one card by id without loading its parent board."""
    match use_case.execute(GetCardQuery(card_id=str(card_id))):
        case Ok(value):
            return to_card_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@cards_write_router.patch("/cards/{card_id}")
def patch_card(
    card_id: UUID,
    body: CardUpdate,
    use_case: PatchCardUseCaseDep,
    actor_id: ActorIdDep,
) -> CardRead:
    """Apply a sparse update and/or move to an existing card."""
    input_data = to_patch_card_input(body)
    command = PatchCardCommand(
        card_id=str(card_id),
        title=input_data["title"],
        description=input_data["description"],
        column_id=input_data["column_id"],
        position=input_data["position"],
        priority=input_data["priority"],
        due_at=input_data["due_at"],
        clear_due_at=input_data["clear_due_at"],
        actor_id=actor_id,
    )
    match use_case.execute(command):
        case Ok(value):
            return to_card_response(value)
        case Err(err):
            raise_http_from_application_error(err)
