"""Application use case for Kanban list boards behavior."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.contracts import AppBoardSummary
from src.features.kanban.application.contracts.mappers import to_app_board_summary
from src.features.kanban.application.errors import ApplicationError
from src.features.kanban.application.ports.outbound.kanban_query_repository import (
    KanbanQueryRepositoryPort,
)
from src.features.kanban.application.queries.list_boards import ListBoardsQuery
from src.platform.shared.result import Ok, Result


@dataclass(slots=True)
class ListBoardsUseCase:
    """Return a lightweight summary for every board in the system."""

    query_repository: KanbanQueryRepositoryPort

    def execute(
        self,
        query: ListBoardsQuery,
    ) -> Result[list[AppBoardSummary], ApplicationError]:
        """Project every persisted board to ``AppBoardSummary``.

        ``query`` currently carries no filters; it is accepted as a
        parameter to keep the signature stable when pagination or
        filtering is added later.
        """
        del query
        return Ok(
            [
                to_app_board_summary(summary)
                for summary in self.query_repository.list_all()
            ]
        )
