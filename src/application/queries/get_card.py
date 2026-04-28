from __future__ import annotations

from dataclasses import dataclass

from src.application.contracts import AppCard
from src.application.contracts.mappers import to_app_card
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.shared import AppErr, ApplicationError, AppOk, AppResult
from src.application.shared.errors import from_domain_error
from src.domain.shared.result import Err


@dataclass(frozen=True, slots=True)
class GetCardQuery:
    card_id: str


def handle_get_card(
    *,
    repository: KanbanQueryRepositoryPort,
    query: GetCardQuery,
) -> AppResult[AppCard, ApplicationError]:
    card_result = repository.find_card_by_id(query.card_id)
    if isinstance(card_result, Err):
        return AppErr(from_domain_error(card_result.error))
    return AppOk(to_app_card(card_result.value))
