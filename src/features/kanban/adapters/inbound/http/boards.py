from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from src.features.kanban.adapters.inbound.http.dependencies import (
    CreateBoardUseCaseDep,
    DeleteBoardUseCaseDep,
    GetBoardUseCaseDep,
    ListBoardsUseCaseDep,
    PatchBoardUseCaseDep,
)
from src.features.kanban.adapters.inbound.http.errors import (
    raise_http_from_application_error,
)
from src.features.kanban.adapters.inbound.http.mappers import (
    to_board_detail_response,
    to_board_summary_response,
    to_create_board_input,
    to_patch_board_input,
)
from src.features.kanban.adapters.inbound.http.schemas import (
    BoardCreate,
    BoardDetail,
    BoardSummary,
    BoardUpdate,
)
from src.features.kanban.application.commands import (
    CreateBoardCommand,
    DeleteBoardCommand,
    PatchBoardCommand,
)
from src.features.kanban.application.queries import GetBoardQuery, ListBoardsQuery
from src.platform.api.dependencies.security import RequireWriteApiKey
from src.platform.shared.result import Err, Ok

boards_read_router = APIRouter(tags=["boards"])
boards_write_router = APIRouter(tags=["boards"], dependencies=[RequireWriteApiKey])


@boards_write_router.post("/boards", status_code=status.HTTP_201_CREATED)
def create_board(
    body: BoardCreate,
    use_case: CreateBoardUseCaseDep,
) -> BoardSummary:
    match use_case.execute(CreateBoardCommand(title=to_create_board_input(body))):
        case Ok(value):
            return to_board_summary_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_read_router.get("/boards")
def list_boards(use_case: ListBoardsUseCaseDep) -> list[BoardSummary]:
    match use_case.execute(ListBoardsQuery()):
        case Ok(value):
            return [to_board_summary_response(board) for board in value]
        case Err(err):
            raise_http_from_application_error(err)


@boards_read_router.get("/boards/{board_id}")
def get_board(board_id: UUID, use_case: GetBoardUseCaseDep) -> BoardDetail:
    match use_case.execute(GetBoardQuery(board_id=str(board_id))):
        case Ok(value):
            return to_board_detail_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_write_router.patch("/boards/{board_id}")
def patch_board(
    board_id: UUID,
    body: BoardUpdate,
    use_case: PatchBoardUseCaseDep,
) -> BoardSummary:
    match use_case.execute(
        PatchBoardCommand(board_id=str(board_id), title=to_patch_board_input(body))
    ):
        case Ok(value):
            return to_board_summary_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_write_router.delete(
    "/boards/{board_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_board(
    board_id: UUID,
    use_case: DeleteBoardUseCaseDep,
) -> None:
    match use_case.execute(DeleteBoardCommand(board_id=str(board_id))):
        case Ok(_):
            return
        case Err(err):
            raise_http_from_application_error(err)
