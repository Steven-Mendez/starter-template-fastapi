from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import cast

from src.application.ports.repository import DUE_AT_UNSET, KanbanRepository
from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.domain.kanban.services.card_movement import (
    reorder_between_columns,
    reorder_within_column,
    validate_card_move,
)
from src.domain.kanban.specifications.card_move import CardMoveCandidate
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


class InMemoryKanbanRepository(KanbanRepository):
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

    def create_column(
        self, board_id: str, title: str
    ) -> Result[Column, KanbanError]:
        if board_id not in self._boards:
            return Err(KanbanError.BOARD_NOT_FOUND)
        existing = [c for c in self._columns.values() if c.board_id == board_id]
        position = max((c.position for c in existing), default=-1) + 1
        column_id = str(uuid.uuid4())
        column = _Column(
            id=column_id,
            board_id=board_id,
            title=title,
            position=position,
        )
        self._columns[column_id] = column
        return Ok(
            Column(
                id=column.id,
                board_id=column.board_id,
                title=column.title,
                position=column.position,
                cards=[],
            )
        )

    def delete_column(self, column_id: str) -> Result[None, KanbanError]:
        if column_id not in self._columns:
            return Err(KanbanError.COLUMN_NOT_FOUND)
        self._delete_column_internal(column_id)
        return Ok(None)

    def _delete_column_internal(self, column_id: str) -> None:
        to_delete = [
            key for key, card in self._cards.items() if card.column_id == column_id
        ]
        for card_id in to_delete:
            del self._cards[card_id]
        self._columns.pop(column_id, None)

    def create_card(
        self,
        column_id: str,
        title: str,
        description: str | None,
        *,
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Result[Card, KanbanError]:
        if column_id not in self._columns:
            return Err(KanbanError.COLUMN_NOT_FOUND)
        position = len([c for c in self._cards.values() if c.column_id == column_id])
        card_id = str(uuid.uuid4())
        card = _Card(
            id=card_id,
            column_id=column_id,
            title=title,
            description=description,
            position=position,
            priority=priority,
            due_at=due_at,
        )
        self._cards[card_id] = card
        return Ok(
            Card(
                id=card.id,
                column_id=card.column_id,
                title=card.title,
                description=card.description,
                position=card.position,
                priority=card.priority,
                due_at=card.due_at,
            )
        )

    def get_card(self, card_id: str) -> Result[Card, KanbanError]:
        card = self._cards.get(card_id)
        if not card:
            return Err(KanbanError.CARD_NOT_FOUND)
        return Ok(
            Card(
                id=card.id,
                column_id=card.column_id,
                title=card.title,
                description=card.description,
                position=card.position,
                priority=card.priority,
                due_at=card.due_at,
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
    ) -> Result[Card, KanbanError]:
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

        old_column_id = card.column_id
        target_column_id = column_id if column_id is not None else old_column_id
        current_column = self._columns.get(old_column_id)
        target_column = self._columns.get(target_column_id)
        candidate = CardMoveCandidate(
            target_column_exists=target_column is not None,
            current_board_id=current_column.board_id if current_column else None,
            target_board_id=target_column.board_id if target_column else None,
        )
        move_error = validate_card_move(candidate)
        if move_error is not None:
            return Err(move_error)

        if target_column_id != old_column_id:
            source_order, target_order = reorder_between_columns(
                moving_card_id=card.id,
                source_ordered_card_ids=[
                    row.id for row in self._cards_for_column_sorted(old_column_id)
                ],
                target_ordered_card_ids=[
                    row.id for row in self._cards_for_column_sorted(target_column_id)
                ],
                requested_position=position,
            )
            self._apply_column_order(old_column_id, source_order)
            self._apply_column_order(target_column_id, target_order)
        elif position is not None:
            ordered_ids = reorder_within_column(
                moving_card_id=card.id,
                ordered_card_ids=[
                    row.id for row in self._cards_for_column_sorted(card.column_id)
                ],
                requested_position=position,
            )
            self._apply_column_order(card.column_id, ordered_ids)

        return self.get_card(card_id)

    def _cards_for_column_sorted(self, column_id: str) -> list[_Card]:
        cards = [c for c in self._cards.values() if c.column_id == column_id]
        cards.sort(key=lambda c: c.position)
        return cards

    def _apply_column_order(self, column_id: str, ordered_card_ids: list[str]) -> None:
        for index, card_id in enumerate(ordered_card_ids):
            card = self._cards[card_id]
            card.column_id = column_id
            card.position = index
