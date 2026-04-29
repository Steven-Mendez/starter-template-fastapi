from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies import (
    CreateColumnUseCaseDep,
    DeleteColumnUseCaseDep,
    WriteApiKeyDep,
)
from src.api.mappers.kanban import to_column_response, to_create_column_input
from src.api.routers._errors import raise_http_from_application_error
from src.api.schemas.kanban import ColumnCreate, ColumnRead
from src.application.commands import CreateColumnCommand, DeleteColumnCommand
from src.application.shared import Err, Ok

columns_router = APIRouter(tags=["columns"])


@columns_router.post(
    "/boards/{board_id}/columns",
    response_model=ColumnRead,
    status_code=status.HTTP_201_CREATED,
)
def create_column(
    board_id: UUID,
    body: ColumnCreate,
    use_case: CreateColumnUseCaseDep,
    _: WriteApiKeyDep,
) -> ColumnRead:
    match use_case.execute(
        CreateColumnCommand(board_id=str(board_id), title=to_create_column_input(body))
    ):
        case Ok(value):
            return to_column_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@columns_router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(
    column_id: UUID,
    use_case: DeleteColumnUseCaseDep,
    _: WriteApiKeyDep,
) -> None:
    match use_case.execute(DeleteColumnCommand(column_id=str(column_id))):
        case Ok(_):
            return
        case Err(err):
            raise_http_from_application_error(err)
