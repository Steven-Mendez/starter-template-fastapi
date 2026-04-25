from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppBoard, AppBoardSummary, AppCard
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.queries.get_board import GetBoardQuery, handle_get_board
from src.application.queries.get_card import GetCardQuery, handle_get_card
from src.application.queries.health_check import HealthCheckQuery, handle_health_check
from src.application.queries.list_boards import ListBoardsQuery, handle_list_boards
from src.application.queries.port import KanbanQueryInputPort
from src.application.shared import ApplicationError, AppResult, ReadinessProbe


@dataclass(slots=True)
class KanbanQueryHandlers(KanbanQueryInputPort):
    repository: KanbanQueryRepositoryPort
    readiness: ReadinessProbe

    def handle_health_check(self, query: HealthCheckQuery) -> bool:
        return handle_health_check(
            readiness=self.readiness,
            query=query,
        )

    def handle_list_boards(
        self,
        query: ListBoardsQuery,
    ) -> AppResult[list[AppBoardSummary], ApplicationError]:
        return handle_list_boards(
            repository=self.repository,
            query=query,
        )

    def handle_get_board(
        self,
        query: GetBoardQuery,
    ) -> AppResult[AppBoard, ApplicationError]:
        return handle_get_board(
            repository=self.repository,
            query=query,
        )

    def handle_get_card(
        self,
        query: GetCardQuery,
    ) -> AppResult[AppCard, ApplicationError]:
        return handle_get_card(
            repository=self.repository,
            query=query,
        )
