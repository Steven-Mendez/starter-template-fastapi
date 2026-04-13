from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

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
from kanban.store import DUE_AT_UNSET, KanbanStore, get_store

router = APIRouter(prefix="/api", tags=["kanban"])


@router.post("/boards", response_model=BoardSummary, status_code=status.HTTP_201_CREATED)
def create_board(
    body: BoardCreate,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> BoardSummary:
    return store.create_board(body.title)


@router.get("/boards", response_model=list[BoardSummary])
def list_boards(store: Annotated[KanbanStore, Depends(get_store)]) -> list[BoardSummary]:
    return store.list_boards()


@router.get("/boards/{board_id}", response_model=BoardDetail)
def get_board(
    board_id: UUID,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> BoardDetail:
    b = store.get_board(str(board_id))
    if not b:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    return b


@router.patch("/boards/{board_id}", response_model=BoardSummary)
def patch_board(
    board_id: UUID,
    body: BoardUpdate,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> BoardSummary:
    if body.title is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    out = store.update_board(str(board_id), body.title)
    if not out:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    return out


@router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(
    board_id: UUID,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> None:
    if not store.delete_board(str(board_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")


@router.post(
    "/boards/{board_id}/columns",
    response_model=ColumnRead,
    status_code=status.HTTP_201_CREATED,
)
def create_column(
    board_id: UUID,
    body: ColumnCreate,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> ColumnRead:
    col = store.create_column(str(board_id), body.title)
    if not col:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    return col


@router.delete("/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_column(
    column_id: UUID,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> None:
    if not store.delete_column(str(column_id)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")


@router.post(
    "/columns/{column_id}/cards",
    response_model=CardRead,
    status_code=status.HTTP_201_CREATED,
)
def create_card(
    column_id: UUID,
    body: CardCreate,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> CardRead:
    card = store.create_card(
        str(column_id),
        body.title,
        body.description,
        priority=body.priority,
        due_at=body.due_at,
    )
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
    return card


@router.get("/cards/{card_id}", response_model=CardRead)
def get_card(
    card_id: UUID,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> CardRead:
    card = store.get_card(str(card_id))
    if not card:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return card


@router.patch("/cards/{card_id}", response_model=CardRead)
def patch_card(
    card_id: UUID,
    body: CardUpdate,
    store: Annotated[KanbanStore, Depends(get_store)],
) -> CardRead:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    col_id = str(updates["column_id"]) if "column_id" in updates else None
    pos = updates.get("position")
    out = store.update_card(
        str(card_id),
        title=updates.get("title"),
        description=updates.get("description"),
        column_id=col_id,
        position=pos,
        priority=updates.get("priority"),
        due_at=updates["due_at"] if "due_at" in updates else DUE_AT_UNSET,
    )
    if not out:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return out
