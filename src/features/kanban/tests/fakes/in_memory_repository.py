from __future__ import annotations

from copy import deepcopy

from src.features.kanban.application.ports.outbound import (
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    KanbanQueryRepositoryPort,
)
from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board, BoardSummary, Card
from src.platform.persistence.readiness import ReadinessProbe
from src.platform.shared.result import Err, Ok, Result


class InMemoryKanbanRepository(
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
    KanbanQueryRepositoryPort,
    ReadinessProbe,
):
    """In-memory adapter implementing every Kanban outbound port.

    Aggregates are stored as deep copies so mutations on the returned object do
    not bleed into the store, mimicking real persistence semantics.
    """

    def __init__(self) -> None:
        self._boards: dict[str, Board] = {}
        self._ready: bool = True

    def is_ready(self) -> bool:
        return self._ready

    def set_ready(self, value: bool) -> None:
        self._ready = value

    def list_all(self) -> list[BoardSummary]:
        return [
            BoardSummary(id=b.id, title=b.title, created_at=b.created_at)
            for b in sorted(self._boards.values(), key=lambda b: b.created_at)
        ]

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        board = self._boards.get(board_id)
        if board is None:
            return Err(KanbanError.BOARD_NOT_FOUND)
        return Ok(deepcopy(board))

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]:
        for board in self._boards.values():
            for column in board.columns:
                for card in column.cards:
                    if card.id == card_id:
                        return Ok(deepcopy(card))
        return Err(KanbanError.CARD_NOT_FOUND)

    def find_board_id_by_card(self, card_id: str) -> str | None:
        for board in self._boards.values():
            for column in board.columns:
                if any(card.id == card_id for card in column.cards):
                    return board.id
        return None

    def find_board_id_by_column(self, column_id: str) -> str | None:
        for board in self._boards.values():
            if any(column.id == column_id for column in board.columns):
                return board.id
        return None

    def remove(self, board_id: str) -> Result[None, KanbanError]:
        if board_id not in self._boards:
            return Err(KanbanError.BOARD_NOT_FOUND)
        del self._boards[board_id]
        return Ok(None)

    def save(self, board: Board) -> None:
        existing = self._boards.get(board.id)
        if existing and existing.version != board.version:
            raise RuntimeError(f"Stale write for board {board.id}")
        new_version = board.version + 1
        snapshot = deepcopy(board)
        snapshot.version = new_version
        self._boards[board.id] = snapshot
        board.version = new_version

    def close(self) -> None:
        pass
