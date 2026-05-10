"""Application use case for Kanban list boards behavior."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.authorization.ports import (
    LOOKUP_MAX_LIMIT,
    AuthorizationPort,
)
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
    """Return the boards the calling user has at least ``read`` on.

    Filtering at the authorization layer (rather than fetching everything
    and post-filtering) keeps the response size proportional to the
    user's access — the canonical ReBAC ``LookupResources`` pattern.
    """

    query_repository: KanbanQueryRepositoryPort
    authorization: AuthorizationPort

    def execute(
        self,
        query: ListBoardsQuery,
    ) -> Result[list[AppBoardSummary], ApplicationError]:
        """Look up readable board ids, then fetch summaries for those ids."""
        if query.actor_id is None:
            # Anonymous callers cannot satisfy any kanban relation. Returning
            # the empty list rather than 401 lets the platform layer continue
            # to enforce authentication uniformly via principal resolution.
            return Ok([])
        board_ids = self.authorization.lookup_resources(
            user_id=query.actor_id,
            action="read",
            resource_type="kanban",
            limit=LOOKUP_MAX_LIMIT,
        )
        if not board_ids:
            return Ok([])
        return Ok(
            [
                to_app_board_summary(summary)
                for summary in self.query_repository.list_by_ids(board_ids)
            ]
        )
