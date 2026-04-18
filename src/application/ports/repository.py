from __future__ import annotations

from datetime import datetime
from typing import Protocol

from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result

DUE_AT_UNSET = object()


class KanbanQueryRepository(Protocol):
    def is_ready(self) -> bool: ...

    def list_boards(self) -> list[BoardSummary]: ...

    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...

    def get_card(self, card_id: str) -> Result[Card, KanbanError]: ...


class KanbanCommandRepository(Protocol):
    def close(self) -> None: ...

    def create_board(self, title: str) -> BoardSummary: ...

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]: ...

    def delete_board(self, board_id: str) -> Result[None, KanbanError]: ...

    def create_column(
        self, board_id: str, title: str
    ) -> Result[Column, KanbanError]: ...

    def delete_column(self, column_id: str) -> Result[None, KanbanError]: ...

    def create_card(
        self,
        column_id: str,
        title: str,
        description: str | None,
        *,
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Result[Card, KanbanError]: ...

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
    ) -> Result[Card, KanbanError]: ...


class KanbanRepository(KanbanQueryRepository, KanbanCommandRepository, Protocol):
    pass
