from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.application.contracts import AppBoardSummary
from src.application.queries.get_card import GetCardQuery, handle_get_card
from src.application.shared import AppErr, ApplicationError, AppOk
from src.domain.kanban.models import Board, Card, CardPriority
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok, Result

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class SpyQueryRepository:
    card_result: Result[Card, KanbanError]
    find_card_by_id_calls: int = 0
    find_by_id_calls: int = 0

    def list_all(self) -> list[AppBoardSummary]:
        return []

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        del board_id
        self.find_by_id_calls += 1
        return Err(KanbanError.BOARD_NOT_FOUND)

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]:
        del card_id
        self.find_card_by_id_calls += 1
        return self.card_result

    def find_board_id_by_card(self, card_id: str) -> str | None:
        del card_id
        return None


def test_handle_get_card_uses_direct_lookup_without_board_read() -> None:
    card = Card(
        id="card-1",
        column_id="column-1",
        title="Task",
        description="desc",
        position=0,
        priority=CardPriority.HIGH,
        due_at=None,
    )
    repository = SpyQueryRepository(card_result=Ok(card))

    result = handle_get_card(
        repository=repository,
        query=GetCardQuery(card_id=card.id),
    )

    assert isinstance(result, AppOk)
    assert result.value.id == card.id
    assert result.value.title == "Task"
    assert repository.find_card_by_id_calls == 1
    assert repository.find_by_id_calls == 0


def test_handle_get_card_maps_missing_card_error() -> None:
    repository = SpyQueryRepository(card_result=Err(KanbanError.CARD_NOT_FOUND))

    result = handle_get_card(
        repository=repository,
        query=GetCardQuery(card_id="missing-card"),
    )

    assert isinstance(result, AppErr)
    assert result.error is ApplicationError.CARD_NOT_FOUND
    assert repository.find_card_by_id_calls == 1
    assert repository.find_by_id_calls == 0
