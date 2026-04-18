from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.application.commands import (
    CreateBoardCommand,
    CreateCardCommand,
    CreateColumnCommand,
    DeleteBoardCommand,
    DeleteColumnCommand,
    KanbanCommandHandlers,
    PatchBoardCommand,
    PatchCardCommand,
)
from src.application.ports.repository import DUE_AT_UNSET, KanbanRepository
from src.application.queries import (
    GetBoardQuery,
    GetCardQuery,
    HealthCheckQuery,
    KanbanQueryHandlers,
    ListBoardsQuery,
)
from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Result


@dataclass(slots=True)
class KanbanUseCases:
    repository: KanbanRepository

    def is_ready(self) -> bool:
        return KanbanQueryHandlers(repository=self.repository).handle_health_check(
            HealthCheckQuery()
        )

    def create_board(self, title: str) -> BoardSummary:
        return KanbanCommandHandlers(repository=self.repository).handle_create_board(
            CreateBoardCommand(title=title)
        )

    def list_boards(self) -> list[BoardSummary]:
        return KanbanQueryHandlers(repository=self.repository).handle_list_boards(
            ListBoardsQuery()
        )

    def get_board(self, board_id: str) -> Result[Board, KanbanError]:
        return KanbanQueryHandlers(repository=self.repository).handle_get_board(
            GetBoardQuery(board_id=board_id)
        )

    def patch_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]:
        return KanbanCommandHandlers(repository=self.repository).handle_patch_board(
            PatchBoardCommand(board_id=board_id, title=title)
        )

    def delete_board(self, board_id: str) -> Result[None, KanbanError]:
        return KanbanCommandHandlers(repository=self.repository).handle_delete_board(
            DeleteBoardCommand(board_id=board_id)
        )

    def create_column(
        self, board_id: str, title: str
    ) -> Result[Column, KanbanError]:
        return KanbanCommandHandlers(repository=self.repository).handle_create_column(
            CreateColumnCommand(board_id=board_id, title=title)
        )

    def delete_column(self, column_id: str) -> Result[None, KanbanError]:
        return KanbanCommandHandlers(repository=self.repository).handle_delete_column(
            DeleteColumnCommand(column_id=column_id)
        )

    def create_card(
        self,
        column_id: str,
        title: str,
        description: str | None,
        *,
        priority: CardPriority,
        due_at: datetime | None,
    ) -> Result[Card, KanbanError]:
        return KanbanCommandHandlers(repository=self.repository).handle_create_card(
            CreateCardCommand(
                column_id=column_id,
                title=title,
                description=description,
                priority=priority,
                due_at=due_at,
            )
        )

    def get_card(self, card_id: str) -> Result[Card, KanbanError]:
        return KanbanQueryHandlers(repository=self.repository).handle_get_card(
            GetCardQuery(card_id=card_id)
        )

    def patch_card(
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
        return KanbanCommandHandlers(repository=self.repository).handle_patch_card(
            PatchCardCommand(
                card_id=card_id,
                title=title,
                description=description,
                column_id=column_id,
                position=position,
                priority=priority,
                due_at=due_at,
            )
        )
