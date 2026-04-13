from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, cast

from kanban.card_move_specifications import (
    CardMoveCandidate,
    SameBoardMoveSpecification,
    TargetColumnExistsSpecification,
)
from kanban.errors import KanbanError
from kanban.result import Err, Ok, Result
from kanban.schemas import BoardDetail, BoardSummary, CardPriority, CardRead, ColumnRead
from settings import AppSettings, get_settings

DUE_AT_UNSET = object()


@dataclass
class _Board:
    id: str
    title: str
    created_at: datetime


@dataclass
class _Column:
    id: str
    board_id: str
    title: str
    position: int


@dataclass
class _Card:
    id: str
    column_id: str
    title: str
    description: str | None
    position: int
    priority: CardPriority
    due_at: datetime | None


class KanbanRepository(Protocol):
    def is_ready(self) -> bool: ...

    def create_board(self, title: str) -> BoardSummary: ...

    def list_boards(self) -> list[BoardSummary]: ...

    def get_board(self, board_id: str) -> Result[BoardDetail, KanbanError]: ...

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]: ...

    def delete_board(self, board_id: str) -> Result[None, KanbanError]: ...

    def create_column(
        self, board_id: str, title: str
    ) -> Result[ColumnRead, KanbanError]: ...

    def delete_column(self, column_id: str) -> Result[None, KanbanError]: ...

    def create_card(
        self,
        column_id: str,
        title: str,
        description: str | None,
        *,
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Result[CardRead, KanbanError]: ...

    def get_card(self, card_id: str) -> Result[CardRead, KanbanError]: ...

    def update_card(
        self,
        card_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        column_id: str | None = None,
        position: int | None = None,
        priority: CardPriority | None = None,
        due_at: datetime | None | object = ...,
    ) -> Result[CardRead, KanbanError]: ...


class InMemoryKanbanRepository(KanbanRepository):
    def __init__(self) -> None:
        self._boards: dict[str, _Board] = {}
        self._columns: dict[str, _Column] = {}
        self._cards: dict[str, _Card] = {}

    def is_ready(self) -> bool:
        return True

    def create_board(self, title: str) -> BoardSummary:
        bid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        row = _Board(id=bid, title=title, created_at=now)
        self._boards[bid] = row
        return BoardSummary(id=row.id, title=row.title, created_at=row.created_at)

    def list_boards(self) -> list[BoardSummary]:
        return [
            BoardSummary(id=b.id, title=b.title, created_at=b.created_at)
            for b in self._boards.values()
        ]

    def get_board(self, board_id: str) -> Result[BoardDetail, KanbanError]:
        b = self._boards.get(board_id)
        if not b:
            return Err(KanbanError.BOARD_NOT_FOUND)
        cols = [c for c in self._columns.values() if c.board_id == board_id]
        cols.sort(key=lambda c: c.position)
        out_cols: list[ColumnRead] = []
        for c in cols:
            cards = self._cards_for_column_sorted(c.id)
            out_cols.append(
                ColumnRead(
                    id=c.id,
                    board_id=c.board_id,
                    title=c.title,
                    position=c.position,
                    cards=[
                        CardRead(
                            id=card.id,
                            column_id=card.column_id,
                            title=card.title,
                            description=card.description,
                            position=card.position,
                            priority=card.priority,
                            due_at=card.due_at,
                        )
                        for card in cards
                    ],
                )
            )
        return Ok(
            BoardDetail(
                id=b.id,
                title=b.title,
                created_at=b.created_at,
                columns=out_cols,
            )
        )

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]:
        b = self._boards.get(board_id)
        if not b:
            return Err(KanbanError.BOARD_NOT_FOUND)
        b.title = title
        return Ok(BoardSummary(id=b.id, title=b.title, created_at=b.created_at))

    def delete_board(self, board_id: str) -> Result[None, KanbanError]:
        if board_id not in self._boards:
            return Err(KanbanError.BOARD_NOT_FOUND)
        col_ids = [c.id for c in self._columns.values() if c.board_id == board_id]
        for cid in col_ids:
            self._delete_column_internal(cid)
        del self._boards[board_id]
        return Ok(None)

    def create_column(
        self, board_id: str, title: str
    ) -> Result[ColumnRead, KanbanError]:
        if board_id not in self._boards:
            return Err(KanbanError.BOARD_NOT_FOUND)
        existing = [c for c in self._columns.values() if c.board_id == board_id]
        pos = max((c.position for c in existing), default=-1) + 1
        cid = str(uuid.uuid4())
        col = _Column(id=cid, board_id=board_id, title=title, position=pos)
        self._columns[cid] = col
        return Ok(
            ColumnRead(
                id=col.id,
                board_id=col.board_id,
                title=col.title,
                position=col.position,
                cards=[],
            )
        )

    def delete_column(self, column_id: str) -> Result[None, KanbanError]:
        if column_id not in self._columns:
            return Err(KanbanError.COLUMN_NOT_FOUND)
        self._delete_column_internal(column_id)
        return Ok(None)

    def _delete_column_internal(self, column_id: str) -> None:
        to_del = [k for k, c in self._cards.items() if c.column_id == column_id]
        for k in to_del:
            del self._cards[k]
        self._columns.pop(column_id, None)

    def create_card(
        self,
        column_id: str,
        title: str,
        description: str | None,
        *,
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Result[CardRead, KanbanError]:
        if column_id not in self._columns:
            return Err(KanbanError.COLUMN_NOT_FOUND)
        n = len([c for c in self._cards.values() if c.column_id == column_id])
        card_id = str(uuid.uuid4())
        card = _Card(
            id=card_id,
            column_id=column_id,
            title=title,
            description=description,
            position=n,
            priority=priority,
            due_at=due_at,
        )
        self._cards[card_id] = card
        return Ok(
            CardRead(
                id=card.id,
                column_id=card.column_id,
                title=card.title,
                description=card.description,
                position=card.position,
                priority=card.priority,
                due_at=card.due_at,
            )
        )

    def get_card(self, card_id: str) -> Result[CardRead, KanbanError]:
        c = self._cards.get(card_id)
        if not c:
            return Err(KanbanError.CARD_NOT_FOUND)
        return Ok(
            CardRead(
                id=c.id,
                column_id=c.column_id,
                title=c.title,
                description=c.description,
                position=c.position,
                priority=c.priority,
                due_at=c.due_at,
            )
        )

    def update_card(
        self,
        card_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        column_id: str | None = None,
        position: int | None = None,
        priority: CardPriority | None = None,
        due_at: datetime | None | object = DUE_AT_UNSET,
    ) -> Result[CardRead, KanbanError]:
        card = self._cards.get(card_id)
        if not card:
            return Err(KanbanError.CARD_NOT_FOUND)

        if title is not None:
            card.title = title
        if description is not None:
            card.description = description
        if priority is not None:
            card.priority = priority
        if due_at is not DUE_AT_UNSET:
            card.due_at = cast(datetime | None, due_at)

        if column_id is None and position is None:
            return self.get_card(card_id)

        old_col = card.column_id
        target_col = column_id if column_id is not None else old_col
        current_column = self._columns.get(old_col)
        target_column = self._columns.get(target_col)
        candidate = CardMoveCandidate(
            target_column_exists=target_column is not None,
            current_board_id=current_column.board_id if current_column else None,
            target_board_id=target_column.board_id if target_column else None,
        )
        if not TargetColumnExistsSpecification().is_satisfied_by(candidate):
            return Err(KanbanError.COLUMN_NOT_FOUND)
        if not SameBoardMoveSpecification().is_satisfied_by(candidate):
            return Err(KanbanError.INVALID_CARD_MOVE)

        if target_col != old_col:
            self._remove_card_and_renumber(old_col, card_id)
            card.column_id = target_col
            if position is None:
                others = [
                    c
                    for c in self._cards.values()
                    if c.column_id == target_col and c.id != card_id
                ]
                card.position = len(others)
            else:
                self._insert_card_at(card, target_col, position)
        elif position is not None:
            self._move_within_column(card, position)

        return self.get_card(card_id)

    def _cards_for_column_sorted(self, column_id: str) -> list[_Card]:
        rows = [c for c in self._cards.values() if c.column_id == column_id]
        rows.sort(key=lambda c: c.position)
        return rows

    def _remove_card_and_renumber(self, column_id: str, card_id: str) -> None:
        remaining = [
            c
            for c in self._cards.values()
            if c.column_id == column_id and c.id != card_id
        ]
        remaining.sort(key=lambda c: c.position)
        for i, c in enumerate(remaining):
            c.position = i

    def _insert_card_at(self, card: _Card, column_id: str, position: int) -> None:
        others = [
            c
            for c in self._cards.values()
            if c.column_id == column_id and c.id != card.id
        ]
        others.sort(key=lambda c: c.position)
        pos = min(max(0, position), len(others))
        ordered = others[:pos] + [card] + others[pos:]
        card.column_id = column_id
        for i, c in enumerate(ordered):
            c.position = i

    def _move_within_column(self, card: _Card, position: int) -> None:
        col_id = card.column_id
        others = [
            c for c in self._cards.values() if c.column_id == col_id and c.id != card.id
        ]
        others.sort(key=lambda c: c.position)
        pos = min(max(0, position), len(others))
        ordered = others[:pos] + [card] + others[pos:]
        for i, c in enumerate(ordered):
            c.position = i


_default_repository: KanbanRepository | None = None
_default_repository_key: tuple[str, str] | None = None


def create_repository_for_settings(settings: AppSettings) -> KanbanRepository:
    if settings.repository_backend == "sqlite":
        from kanban.sqlite_repository import SQLiteKanbanRepository

        return SQLiteKanbanRepository(settings.sqlite_path)
    return InMemoryKanbanRepository()


def get_repository() -> KanbanRepository:
    global _default_repository, _default_repository_key
    settings = get_settings()
    key = (settings.repository_backend, settings.sqlite_path)
    if _default_repository is None or _default_repository_key != key:
        _default_repository = create_repository_for_settings(settings)
        _default_repository_key = key
    return _default_repository


def set_repository_for_tests(repo: KanbanRepository) -> None:
    global _default_repository, _default_repository_key
    _default_repository = repo
    _default_repository_key = None
