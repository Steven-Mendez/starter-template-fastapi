"""FastAPI routes for Kanban column resources."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from src.features.kanban.adapters.inbound.http.dependencies import (
    ActorIdDep,
    CreateColumnUseCaseDep,
    DeleteColumnUseCaseDep,
)
from src.features.kanban.adapters.inbound.http.errors import (
    raise_http_from_application_error,
)
from src.features.kanban.adapters.inbound.http.mappers import (
    to_column_response,
    to_create_column_input,
)
from src.features.kanban.adapters.inbound.http.schemas import ColumnCreate, ColumnRead
from src.features.kanban.application.commands import (
    CreateColumnCommand,
    DeleteColumnCommand,
)
from src.platform.shared.result import Err, Ok

columns_write_router = APIRouter(tags=["columns"])


@columns_write_router.post(
    "/boards/{board_id}/columns",
    status_code=status.HTTP_201_CREATED,
)
def create_column(
    board_id: UUID,
    body: ColumnCreate,
    use_case: CreateColumnUseCaseDep,
    actor_id: ActorIdDep,
) -> ColumnRead:
    """Append a new column to the given board and return its public projection."""
    command = CreateColumnCommand(
        board_id=str(board_id),
        title=to_create_column_input(body),
        actor_id=actor_id,
    )
    match use_case.execute(command):
        case Ok(value):
            return to_column_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@columns_write_router.delete(
    "/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_column(
    column_id: UUID,
    use_case: DeleteColumnUseCaseDep,
    actor_id: ActorIdDep,
) -> None:
    """Delete a column and re-compact the remaining column positions on the board."""
    command = DeleteColumnCommand(column_id=str(column_id), actor_id=actor_id)
    match use_case.execute(command):
        case Ok(_):
            return
        case Err(err):
            raise_http_from_application_error(err)
