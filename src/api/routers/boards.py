from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import CommandHandlersDep, QueryHandlersDep
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
from src.application.shared import AppErr, AppOk

boards_router = APIRouter(tags=["boards"])


@boards_router.post(
    "/boards", response_model=BoardSummary, status_code=status.HTTP_201_CREATED
)
def create_board(
    body: BoardCreate,
    commands: CommandHandlersDep,
) -> BoardSummary:
    match commands.handle_create_board(
        CreateBoardCommand(title=to_create_board_input(body))
    ):
        case AppOk(value):
            return to_board_summary_response(value)
        case AppErr(err):
            raise_http_from_application_error(err)


@boards_router.get("/boards", response_model=list[BoardSummary])
def list_boards(
    queries: QueryHandlersDep,
) -> list[BoardSummary]:
    match queries.handle_list_boards(ListBoardsQuery()):
        case AppOk(value):
            return [to_board_summary_response(board) for board in value]
        case AppErr(err):
            raise_http_from_application_error(err)


@boards_router.get("/boards/{board_id}", response_model=BoardDetail)
def get_board(
    board_id: UUID,
    queries: QueryHandlersDep,
) -> BoardDetail:
    match queries.handle_get_board(GetBoardQuery(board_id=str(board_id))):
        case AppOk(value):
            return to_board_detail_response(value)
        case AppErr(err):
            raise_http_from_application_error(err)


@boards_router.patch("/boards/{board_id}", response_model=BoardSummary)
def patch_board(
    board_id: UUID,
    body: BoardUpdate,
    commands: CommandHandlersDep,
) -> BoardSummary:
    title = to_patch_board_input(body)
    if title is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    match commands.handle_patch_board(
        PatchBoardCommand(board_id=str(board_id), title=title)
    ):
        case AppOk(value):
            return to_board_summary_response(value)
        case AppErr(err):
            raise_http_from_application_error(err)


@boards_router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board_id: UUID,
    commands: CommandHandlersDep,
) -> None:
    match commands.handle_delete_board(DeleteBoardCommand(board_id=str(board_id))):
        case AppOk(_):
            return
        case AppErr(err):
            raise_http_from_application_error(err)
