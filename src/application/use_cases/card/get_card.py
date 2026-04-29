from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppCard
from src.application.contracts.mappers import to_app_card
from src.application.kanban.errors import ApplicationError, from_domain_error
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.queries.get_card import GetCardQuery
from src.domain.shared.result import Err, Ok, Result


@dataclass(slots=True)
class GetCardUseCase:
    query_repository: KanbanQueryRepositoryPort

    def execute(self, query: GetCardQuery) -> Result[AppCard, ApplicationError]:
        card_result = self.query_repository.find_card_by_id(query.card_id)
        if isinstance(card_result, Err):
            return Err(from_domain_error(card_result.error))
        return Ok(to_app_card(card_result.value))
