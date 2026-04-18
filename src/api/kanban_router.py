from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import get_kanban_command_handlers, get_kanban_query_handlers
from src.api.mappers.kanban import (
    to_board_detail_response,
    to_board_summary_response,
    to_card_response,
    to_column_response,
    to_create_board_input,
    to_create_card_input,
    to_create_column_input,
    to_patch_board_input,
    to_patch_card_input,
)
from src.api.schemas.kanban import (
    BoardCreate,
    BoardDetail,
    BoardSummary,
    BoardUpdate,
    CardCreate,
    CardRead,
    CardUpdate,
    ColumnCreate,
    ColumnRead,
)
from src.application.commands import (
    CreateBoardCommand,
    CreateCardCommand,
    CreateColumnCommand,
    DeleteBoardCommand,
    DeleteColumnCommand,
    KanbanCommandHandlers,
    PatchBoardCommand,
    PatchCardCommand,
)
from src.application.ports.repository import DUE_AT_UNSET
from src.application.queries import (
    GetBoardQuery,
    GetCardQuery,
    KanbanQueryHandlers,
    ListBoardsQuery,
)
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok

kanban_router = APIRouter(prefix="/api", tags=["kanban"])


def _http_from_kanban_error(err: KanbanError) -> NoReturn:
    status_code = status.HTTP_404_NOT_FOUND
    if err is KanbanError.INVALID_CARD_MOVE:
        status_code = status.HTTP_409_CONFLICT
    raise HTTPException(status_code=status_code, detail=err.detail)


@kanban_router.post(
    "/boards", response_model=BoardSummary, status_code=status.HTTP_201_CREATED
)
def create_board(
    body: BoardCreate,
    commands: Annotated[KanbanCommandHandlers, Depends(get_kanban_command_handlers)],
) -> BoardSummary:
    return to_board_summary_response(
        commands.handle_create_board(
            CreateBoardCommand(title=to_create_board_input(body))
        )
    )


@kanban_router.get("/boards", response_model=list[BoardSummary])
def list_boards(
    queries: Annotated[KanbanQueryHandlers, Depends(get_kanban_query_handlers)],
) -> list[BoardSummary]:
    return [
        to_board_summary_response(board)
        for board in queries.handle_list_boards(ListBoardsQuery())
    ]


@kanban_router.get("/boards/{board_id}", response_model=BoardDetail)
def get_board(
    board_id: UUID,
    queries: Annotated[KanbanQueryHandlers, Depends(get_kanban_query_handlers)],
) -> BoardDetail:
    match queries.handle_get_board(GetBoardQuery(board_id=str(board_id))):
        case Ok(value):
            return to_board_detail_response(value)
        case Err(err):
            _http_from_kanban_error(err)


@kanban_router.patch("/boards/{board_id}", response_model=BoardSummary)
def patch_board(
    board_id: UUID,
    body: BoardUpdate,
    commands: Annotated[KanbanCommandHandlers, Depends(get_kanban_command_handlers)],
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
        case Ok(value):
            return to_board_summary_response(value)
        case Err(err):
            _http_from_kanban_error(err)


@kanban_router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board_id: UUID,
    commands: Annotated[KanbanCommandHandlers, Depends(get_kanban_command_handlers)],
) -> None:
    match commands.handle_delete_board(DeleteBoardCommand(board_id=str(board_id))):
        case Ok(_):
            return
        case Err(err):
            _http_from_kanban_error(err)


@kanban_router.post(
    "/boards/{board_id}/columns",
    response_model=ColumnRead,
    status_code=status.HTTP_201_CREATED,
)
def create_column(
    board_id: UUID,
    body: ColumnCreate,
    commands: Annotated[KanbanCommandHandlers, Depends(get_kanban_command_handlers)],
) -> ColumnRead:
    match commands.handle_create_column(
        CreateColumnCommand(board_id=str(board_id), title=to_create_column_input(body))
    ):
        case Ok(value):
            return to_column_response(value)
        case Err(err):
            _http_from_kanban_error(err)


@kanban_router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(
    column_id: UUID,
    commands: Annotated[KanbanCommandHandlers, Depends(get_kanban_command_handlers)],
) -> None:
    match commands.handle_delete_column(DeleteColumnCommand(column_id=str(column_id))):
        case Ok(_):
            return
        case Err(err):
            _http_from_kanban_error(err)


@kanban_router.post(
    "/columns/{column_id}/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
)
def create_card(
    column_id: UUID,
    body: CardCreate,
    commands: Annotated[KanbanCommandHandlers, Depends(get_kanban_command_handlers)],
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
        case Ok(value):
            return to_card_response(value)
        case Err(err):
            _http_from_kanban_error(err)


@kanban_router.get("/cards/{card_id}", response_model=CardRead)
def get_card(
    card_id: UUID,
    queries: Annotated[KanbanQueryHandlers, Depends(get_kanban_query_handlers)],
) -> CardRead:
    match queries.handle_get_card(GetCardQuery(card_id=str(card_id))):
        case Ok(value):
            return to_card_response(value)
        case Err(err):
            _http_from_kanban_error(err)


@kanban_router.patch("/cards/{card_id}", response_model=CardRead)
def patch_card(
    card_id: UUID,
    body: CardUpdate,
    commands: Annotated[KanbanCommandHandlers, Depends(get_kanban_command_handlers)],
) -> CardRead:
    input_data = to_patch_card_input(body, DUE_AT_UNSET)
    if (
        input_data["title"] is None
        and input_data["description"] is None
        and input_data["column_id"] is None
        and input_data["position"] is None
        and input_data["priority"] is None
        and input_data["due_at"] is DUE_AT_UNSET
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    match commands.handle_patch_card(
        PatchCardCommand(
            card_id=str(card_id),
            title=input_data["title"],
            description=input_data["description"],
            column_id=input_data["column_id"],
            position=input_data["position"],
            priority=input_data["priority"],
            due_at=input_data["due_at"],
        )
    ):
        case Ok(value):
            return to_card_response(value)
        case Err(err):
            _http_from_kanban_error(err)
