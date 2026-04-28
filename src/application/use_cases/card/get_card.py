from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppCard
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.queries.get_card import GetCardQuery, handle_get_card
from src.application.shared import ApplicationError, AppResult


@dataclass(slots=True)
class GetCardUseCase:
    query_repository: KanbanQueryRepositoryPort

    def execute(self, query: GetCardQuery) -> AppResult[AppCard, ApplicationError]:
        return handle_get_card(repository=self.query_repository, query=query)
