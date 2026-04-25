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
    board_id = repository.find_board_id_by_card(query.card_id)
    if board_id is None:
        return AppErr(ApplicationError.CARD_NOT_FOUND)

    board_result = repository.find_by_id(board_id)
    if isinstance(board_result, Err):
        return AppErr(from_domain_error(board_result.error))

    for column in board_result.value.columns:
        for card in column.cards:
            if card.id == query.card_id:
                return AppOk(to_app_card(card))
    return AppErr(ApplicationError.CARD_NOT_FOUND)
