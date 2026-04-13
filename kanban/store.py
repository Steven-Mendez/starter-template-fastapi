from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from kanban.schemas import BoardDetail, BoardSummary, CardPriority, CardRead, ColumnRead


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


class KanbanStore:
    def __init__(self) -> None:
        self._boards: dict[str, _Board] = {}
        self._columns: dict[str, _Column] = {}
        self._cards: dict[str, _Card] = {}

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

    def get_board(self, board_id: str) -> BoardDetail | None:
        b = self._boards.get(board_id)
        if not b:
            return None
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
                        )
                        for card in cards
                    ],
                )
            )
        return BoardDetail(
            id=b.id,
            title=b.title,
            created_at=b.created_at,
            columns=out_cols,
        )

    def update_board(self, board_id: str, title: str) -> BoardSummary | None:
        b = self._boards.get(board_id)
        if not b:
            return None
        b.title = title
        return BoardSummary(id=b.id, title=b.title, created_at=b.created_at)

    def delete_board(self, board_id: str) -> bool:
        if board_id not in self._boards:
            return False
        col_ids = [c.id for c in self._columns.values() if c.board_id == board_id]
        for cid in col_ids:
            self._delete_column_internal(cid)
        del self._boards[board_id]
        return True

    def create_column(self, board_id: str, title: str) -> ColumnRead | None:
        if board_id not in self._boards:
            return None
        existing = [c for c in self._columns.values() if c.board_id == board_id]
        pos = max((c.position for c in existing), default=-1) + 1
        cid = str(uuid.uuid4())
        col = _Column(id=cid, board_id=board_id, title=title, position=pos)
        self._columns[cid] = col
        return ColumnRead(
            id=col.id,
            board_id=col.board_id,
            title=col.title,
            position=col.position,
            cards=[],
        )

    def delete_column(self, column_id: str) -> bool:
        if column_id not in self._columns:
            return False
        self._delete_column_internal(column_id)
        return True

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
    ) -> CardRead | None:
        if column_id not in self._columns:
            return None
        n = len([c for c in self._cards.values() if c.column_id == column_id])
        card_id = str(uuid.uuid4())
        card = _Card(
            id=card_id,
            column_id=column_id,
            title=title,
            description=description,
            position=n,
            priority=priority,
        )
        self._cards[card_id] = card
        return CardRead(
            id=card.id,
            column_id=card.column_id,
            title=card.title,
            description=card.description,
            position=card.position,
            priority=card.priority,
        )

    def get_card(self, card_id: str) -> CardRead | None:
        c = self._cards.get(card_id)
        if not c:
            return None
        return CardRead(
            id=c.id,
            column_id=c.column_id,
            title=c.title,
            description=c.description,
            position=c.position,
            priority=c.priority,
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
    ) -> CardRead | None:
        card = self._cards.get(card_id)
        if not card:
            return None

        if title is not None:
            card.title = title
        if description is not None:
            card.description = description
        if priority is not None:
            card.priority = priority

        if column_id is None and position is None:
            return self.get_card(card_id)

        old_col = card.column_id
        target_col = column_id if column_id is not None else old_col

        if target_col not in self._columns:
            return None
        if self._columns[old_col].board_id != self._columns[target_col].board_id:
            return None

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
            c
            for c in self._cards.values()
            if c.column_id == col_id and c.id != card.id
        ]
        others.sort(key=lambda c: c.position)
        pos = min(max(0, position), len(others))
        ordered = others[:pos] + [card] + others[pos:]
        for i, c in enumerate(ordered):
            c.position = i


def get_store() -> KanbanStore:
    return _default_store


_default_store = KanbanStore()
