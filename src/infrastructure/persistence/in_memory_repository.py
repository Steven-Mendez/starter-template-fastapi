from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.domain.kanban.repository import KanbanRepositoryPort
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok, Result


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


class InMemoryKanbanRepository(KanbanRepositoryPort):
    def __init__(self) -> None:
        self._boards: dict[str, _Board] = {}
        self._columns: dict[str, _Column] = {}
        self._cards: dict[str, _Card] = {}

    def close(self) -> None:
        return None

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

    def get_board(self, board_id: str) -> Result[Board, KanbanError]:
        board = self._boards.get(board_id)
        if not board:
            return Err(KanbanError.BOARD_NOT_FOUND)
        columns = [c for c in self._columns.values() if c.board_id == board_id]
        columns.sort(key=lambda c: c.position)
        out_columns: list[Column] = []
        for column in columns:
            cards = self._cards_for_column_sorted(column.id)
            out_columns.append(
                Column(
                    id=column.id,
                    board_id=column.board_id,
                    title=column.title,
                    position=column.position,
                    cards=[
                        Card(
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
            Board(
                id=board.id,
                title=board.title,
                created_at=board.created_at,
                columns=out_columns,
            )
        )

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]:
        board = self._boards.get(board_id)
        if not board:
            return Err(KanbanError.BOARD_NOT_FOUND)
        board.title = title
        return Ok(
            BoardSummary(id=board.id, title=board.title, created_at=board.created_at)
        )

    def delete_board(self, board_id: str) -> Result[None, KanbanError]:
        if board_id not in self._boards:
            return Err(KanbanError.BOARD_NOT_FOUND)
        column_ids = [c.id for c in self._columns.values() if c.board_id == board_id]
        for column_id in column_ids:
            self._delete_column_internal(column_id)
        del self._boards[board_id]
        return Ok(None)

    def _delete_column_internal(self, column_id: str) -> None:
        to_delete = [
            key for key, card in self._cards.items() if card.column_id == column_id
        ]
        for card_id in to_delete:
            del self._cards[card_id]
        self._columns.pop(column_id, None)

    def find_board_id_by_card(self, card_id: str) -> str | None:
        card = self._cards.get(card_id)
        if not card:
            return None
        col = self._columns.get(card.column_id)
        if not col:
            return None
        return col.board_id

    def find_board_id_by_column(self, column_id: str) -> str | None:
        column = self._columns.get(column_id)
        if column is None:
            return None
        return column.board_id

    def save_board(self, board: Board) -> Result[None, KanbanError]:
        if board.id not in self._boards:
            return Err(KanbanError.BOARD_NOT_FOUND)
        self._boards[board.id].title = board.title

        existing_column_ids = {
            column.id
            for column in self._columns.values()
            if column.board_id == board.id
        }
        current_column_ids = {column.id for column in board.columns}
        for column_id in existing_column_ids - current_column_ids:
            self._delete_column_internal(column_id)

        for col in board.columns:
            if col.id not in self._columns:
                self._columns[col.id] = _Column(
                    id=col.id, board_id=board.id, title=col.title, position=col.position
                )
            else:
                c = self._columns[col.id]
                c.title = col.title
                c.position = col.position
            for card in col.cards:
                if card.id not in self._cards:
                    self._cards[card.id] = _Card(
                        id=card.id,
                        column_id=col.id,
                        title=card.title,
                        description=card.description,
                        position=card.position,
                        priority=card.priority,
                        due_at=card.due_at,
                    )
                else:
                    c_model = self._cards[card.id]
                    c_model.column_id = col.id
                    c_model.title = card.title
                    c_model.description = card.description
                    c_model.position = card.position
                    c_model.priority = card.priority
                    c_model.due_at = card.due_at

        existing_card_ids = {
            card.id
            for card in self._cards.values()
            if card.column_id in current_column_ids
        }
        current_card_ids = {
            card.id for column in board.columns for card in column.cards
        }
        for card_id in existing_card_ids - current_card_ids:
            self._cards.pop(card_id, None)

        return Ok(None)

    def _cards_for_column_sorted(self, column_id: str) -> list[_Card]:
        cards = [c for c in self._cards.values() if c.column_id == column_id]
        cards.sort(key=lambda c: c.position)
        return cards
