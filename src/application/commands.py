from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.ports.repository import DUE_AT_UNSET, KanbanCommandRepository
from src.domain.kanban.models import BoardSummary, Card, CardPriority, Column
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result


@dataclass(frozen=True, slots=True)
class CreateBoardCommand:
    title: str


@dataclass(frozen=True, slots=True)
class PatchBoardCommand:
    board_id: str
    title: str


@dataclass(frozen=True, slots=True)
class DeleteBoardCommand:
    board_id: str


@dataclass(frozen=True, slots=True)
class CreateColumnCommand:
    board_id: str
    title: str


@dataclass(frozen=True, slots=True)
class DeleteColumnCommand:
    column_id: str


@dataclass(frozen=True, slots=True)
class CreateCardCommand:
    column_id: str
    title: str
    description: str | None
    priority: CardPriority
    due_at: datetime | None


@dataclass(frozen=True, slots=True)
class PatchCardCommand:
    card_id: str
    title: str | None = None
    description: str | None = None
    column_id: str | None = None
    position: int | None = None
    priority: CardPriority | None = None
    due_at: datetime | None | object = DUE_AT_UNSET


@dataclass(slots=True)
class KanbanCommandHandlers:
    repository: KanbanCommandRepository

    def handle_create_board(self, command: CreateBoardCommand) -> BoardSummary:
        return self.repository.create_board(command.title)

    def handle_patch_board(
        self, command: PatchBoardCommand
    ) -> Result[BoardSummary, KanbanError]:
        return self.repository.update_board(command.board_id, command.title)

    def handle_delete_board(
        self, command: DeleteBoardCommand
    ) -> Result[None, KanbanError]:
        return self.repository.delete_board(command.board_id)

    def handle_create_column(
        self, command: CreateColumnCommand
    ) -> Result[Column, KanbanError]:
        return self.repository.create_column(command.board_id, command.title)

    def handle_delete_column(
        self, command: DeleteColumnCommand
    ) -> Result[None, KanbanError]:
        return self.repository.delete_column(command.column_id)

    def handle_create_card(
        self, command: CreateCardCommand
    ) -> Result[Card, KanbanError]:
        return self.repository.create_card(
            command.column_id,
            command.title,
            command.description,
            priority=command.priority,
            due_at=command.due_at,
        )

    def handle_patch_card(self, command: PatchCardCommand) -> Result[Card, KanbanError]:
        return self.repository.update_card(
            command.card_id,
            title=command.title,
            description=command.description,
            column_id=command.column_id,
            position=command.position,
            priority=command.priority,
            due_at=command.due_at,
        )
