from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies import CommandHandlersDep, QueryHandlersDep, WriteApiKeyDep
from src.api.mappers.kanban import (
    to_card_response,
    to_create_card_input,
    to_patch_card_input,
)
from src.api.routers._errors import raise_http_from_application_error
from src.api.schemas.kanban import CardCreate, CardRead, CardUpdate
from src.application.commands import CreateCardCommand, PatchCardCommand
from src.application.queries import GetCardQuery
from src.application.shared import AppErr, AppOk

cards_router = APIRouter(tags=["cards"])


@cards_router.post(
    "/columns/{column_id}/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
)
def create_card(
    column_id: UUID,
    body: CardCreate,
    commands: CommandHandlersDep,
    _: WriteApiKeyDep,
) -> CardRead:
    title, description, priority, due_at = to_create_card_input(body)
    match commands.handle_create_card(
        CreateCardCommand(
            column_id=str(column_id),
            title=title,
            description=description,
            priority=priority,
            due_at=due_at,
        )
    ):
        case AppOk(value):
            return to_card_response(value)
        case AppErr(err):
            raise_http_from_application_error(err)


@cards_router.get("/cards/{card_id}", response_model=CardRead)
def get_card(
    card_id: UUID,
    queries: QueryHandlersDep,
) -> CardRead:
    match queries.handle_get_card(GetCardQuery(card_id=str(card_id))):
        case AppOk(value):
            return to_card_response(value)
        case AppErr(err):
            raise_http_from_application_error(err)


@cards_router.patch("/cards/{card_id}", response_model=CardRead)
def patch_card(
    card_id: UUID,
    body: CardUpdate,
    commands: CommandHandlersDep,
    _: WriteApiKeyDep,
) -> CardRead:
    input_data = to_patch_card_input(body)
    match commands.handle_patch_card(
        PatchCardCommand(
            card_id=str(card_id),
            title=input_data["title"],
            description=input_data["description"],
            column_id=input_data["column_id"],
            position=input_data["position"],
            priority=input_data["priority"],
            due_at=input_data["due_at"],
            clear_due_at=input_data["clear_due_at"],
        )
    ):
        case AppOk(value):
            return to_card_response(value)
        case AppErr(err):
            raise_http_from_application_error(err)
