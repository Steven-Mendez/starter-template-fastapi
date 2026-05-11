"""In-memory test fake that implements every Kanban outbound port."""

from __future__ import annotations

from copy import deepcopy
from uuid import UUID

from src.features.kanban.application.persistence_errors import PersistenceConflictError
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
    not bleed into the store, mimicking real persistence semantics. A
    parallel ``_tombstones`` dict mirrors the real repository's soft-delete
    semantics so tests against the fake exercise the same behaviour.
    """

    def __init__(self) -> None:
        self._boards: dict[str, Board] = {}
        # Maps board id → (board snapshot, deletion_id) so ``restore`` can
        # revert the exact aggregate that was removed.
        self._tombstones: dict[str, tuple[Board, UUID]] = {}
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

    def list_by_ids(self, board_ids: list[str]) -> list[BoardSummary]:
        if not board_ids:
            return []
        wanted = set(board_ids)
        return [
            BoardSummary(id=b.id, title=b.title, created_at=b.created_at)
            for b in sorted(self._boards.values(), key=lambda b: b.created_at)
            if b.id in wanted
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

    def find_column_id_by_card(self, card_id: str) -> str | None:
        for board in self._boards.values():
            for column in board.columns:
                if any(card.id == card_id for card in column.cards):
                    return column.id
        return None

    def remove(
        self, board_id: str, *, actor_id: UUID | None = None
    ) -> Result[None, KanbanError]:
        if board_id not in self._boards:
            return Err(KanbanError.BOARD_NOT_FOUND)
        from uuid import uuid4

        snapshot = self._boards.pop(board_id)
        snapshot.updated_by = actor_id
        self._tombstones[board_id] = (snapshot, uuid4())
        return Ok(None)

    def restore(
        self, board_id: str, *, actor_id: UUID | None = None
    ) -> Result[None, KanbanError]:
        if board_id not in self._tombstones:
            return Err(KanbanError.BOARD_NOT_FOUND)
        snapshot, _ = self._tombstones.pop(board_id)
        snapshot.updated_by = actor_id
        self._boards[board_id] = snapshot
        return Ok(None)

    def save(self, board: Board) -> None:
        existing = self._boards.get(board.id)
        if existing and existing.version != board.version:
            raise PersistenceConflictError(f"Stale write for board {board.id}")
        new_version = board.version + 1
        snapshot = deepcopy(board)
        snapshot.version = new_version
        self._boards[board.id] = snapshot
        board.version = new_version

    def close(self) -> None:
        pass
