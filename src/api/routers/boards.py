from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from src.api.dependencies import (
    CreateBoardUseCaseDep,
    DeleteBoardUseCaseDep,
    GetBoardUseCaseDep,
    ListBoardsUseCaseDep,
    PatchBoardUseCaseDep,
    WriteApiKeyDep,
)
from src.api.mappers.kanban import (
    to_board_detail_response,
    to_board_summary_response,
    to_create_board_input,
    to_patch_board_input,
)
from src.api.routers._errors import raise_http_from_application_error
from src.api.schemas.kanban import BoardCreate, BoardDetail, BoardSummary, BoardUpdate
from src.application.commands import (
    CreateBoardCommand,
    DeleteBoardCommand,
    PatchBoardCommand,
)
from src.application.queries import GetBoardQuery, ListBoardsQuery
from src.application.shared import Err, Ok

boards_router = APIRouter(tags=["boards"])


@boards_router.post(
    "/boards", response_model=BoardSummary, status_code=status.HTTP_201_CREATED
)
def create_board(
    body: BoardCreate,
    use_case: CreateBoardUseCaseDep,
    _: WriteApiKeyDep,
) -> BoardSummary:
    match use_case.execute(CreateBoardCommand(title=to_create_board_input(body))):
        case Ok(value):
            return to_board_summary_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_router.get("/boards", response_model=list[BoardSummary])
def list_boards(
    use_case: ListBoardsUseCaseDep,
) -> list[BoardSummary]:
    match use_case.execute(ListBoardsQuery()):
        case Ok(value):
            return [to_board_summary_response(board) for board in value]
        case Err(err):
            raise_http_from_application_error(err)


@boards_router.get("/boards/{board_id}", response_model=BoardDetail)
def get_board(
    board_id: UUID,
    use_case: GetBoardUseCaseDep,
) -> BoardDetail:
    match use_case.execute(GetBoardQuery(board_id=str(board_id))):
        case Ok(value):
            return to_board_detail_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_router.patch("/boards/{board_id}", response_model=BoardSummary)
def patch_board(
    board_id: UUID,
    body: BoardUpdate,
    use_case: PatchBoardUseCaseDep,
    _: WriteApiKeyDep,
) -> BoardSummary:
    match use_case.execute(
        PatchBoardCommand(board_id=str(board_id), title=to_patch_board_input(body))
    ):
        case Ok(value):
            return to_board_summary_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board_id: UUID,
    use_case: DeleteBoardUseCaseDep,
    _: WriteApiKeyDep,
) -> None:
    match use_case.execute(DeleteBoardCommand(board_id=str(board_id))):
        case Ok(_):
            return
        case Err(err):
            raise_http_from_application_error(err)
