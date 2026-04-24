from __future__ import annotations

from typing import Protocol

from src.application.contracts import AppBoard, AppBoardSummary, AppCard
from src.application.queries.get_board import GetBoardQuery
from src.application.queries.get_card import GetCardQuery
from src.application.queries.health_check import HealthCheckQuery
from src.application.queries.list_boards import ListBoardsQuery
from src.application.shared import ApplicationError, AppResult


class KanbanQueryPort(Protocol):
    def handle_health_check(self, query: HealthCheckQuery) -> bool: ...

    def handle_list_boards(self, query: ListBoardsQuery) -> list[AppBoardSummary]: ...

    def handle_get_board(
        self,
        query: GetBoardQuery,
    ) -> AppResult[AppBoard, ApplicationError]: ...

    def handle_get_card(
        self,
        query: GetCardQuery,
    ) -> AppResult[AppCard, ApplicationError]: ...
