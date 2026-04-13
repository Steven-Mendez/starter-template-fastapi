from __future__ import annotations

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from dependencies import get_kanban_repository
from kanban.errors import KanbanError
from kanban.repository import KanbanRepository
from kanban.result import Err, Ok
from kanban.schemas import (
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
from kanban.store import DUE_AT_UNSET

router = APIRouter(prefix="/api", tags=["kanban"])


def _http_from_kanban_error(err: KanbanError) -> NoReturn:
    status_code = status.HTTP_404_NOT_FOUND
    if err is KanbanError.INVALID_CARD_MOVE:
        status_code = status.HTTP_409_CONFLICT
    raise HTTPException(
        status_code=status_code,
        detail=err.detail,
    )


@router.post(
    "/boards", response_model=BoardSummary, status_code=status.HTTP_201_CREATED
)
def create_board(
    body: BoardCreate,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> BoardSummary:
    return store.create_board(body.title)


@router.get("/boards", response_model=list[BoardSummary])
def list_boards(
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> list[BoardSummary]:
    return store.list_boards()


@router.get("/boards/{board_id}", response_model=BoardDetail)
def get_board(
    board_id: UUID,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> BoardDetail:
    match store.get_board(str(board_id)):
        case Ok(value):
            return value
        case Err(err):
            _http_from_kanban_error(err)


@router.patch("/boards/{board_id}", response_model=BoardSummary)
def patch_board(
    board_id: UUID,
    body: BoardUpdate,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> BoardSummary:
    if body.title is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    match store.update_board(str(board_id), body.title):
        case Ok(value):
            return value
        case Err(err):
            _http_from_kanban_error(err)


@router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board_id: UUID,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> None:
    match store.delete_board(str(board_id)):
        case Ok(_):
            return
        case Err(err):
            _http_from_kanban_error(err)


@router.post(
    "/boards/{board_id}/columns",
    response_model=ColumnRead,
    status_code=status.HTTP_201_CREATED,
)
def create_column(
    board_id: UUID,
    body: ColumnCreate,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> ColumnRead:
    match store.create_column(str(board_id), body.title):
        case Ok(value):
            return value
        case Err(err):
            _http_from_kanban_error(err)


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(
    column_id: UUID,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> None:
    match store.delete_column(str(column_id)):
        case Ok(_):
            return
        case Err(err):
            _http_from_kanban_error(err)


@router.post(
    "/columns/{column_id}/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
)
def create_card(
    column_id: UUID,
    body: CardCreate,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> CardRead:
    match store.create_card(
        str(column_id),
        body.title,
        body.description,
        priority=body.priority,
        due_at=body.due_at,
    ):
        case Ok(value):
            return value
        case Err(err):
            _http_from_kanban_error(err)


@router.get("/cards/{card_id}", response_model=CardRead)
def get_card(
    card_id: UUID,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> CardRead:
    match store.get_card(str(card_id)):
        case Ok(value):
            return value
        case Err(err):
            _http_from_kanban_error(err)


@router.patch("/cards/{card_id}", response_model=CardRead)
def patch_card(
    card_id: UUID,
    body: CardUpdate,
    store: Annotated[KanbanRepository, Depends(get_kanban_repository)],
) -> CardRead:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    col_id = str(updates["column_id"]) if "column_id" in updates else None
    pos = updates.get("position")
    match store.update_card(
        str(card_id),
        title=updates.get("title"),
        description=updates.get("description"),
        column_id=col_id,
        position=pos,
        priority=updates.get("priority"),
        due_at=updates["due_at"] if "due_at" in updates else DUE_AT_UNSET,
    ):
        case Ok(value):
            return value
        case Err(err):
            _http_from_kanban_error(err)
