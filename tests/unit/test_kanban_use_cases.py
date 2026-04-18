from __future__ import annotations

import pytest

from src.application.use_cases import KanbanUseCases
from src.domain.kanban.models import CardPriority
from src.domain.shared.result import Err, Ok
from src.infrastructure.persistence.in_memory_repository import (
    InMemoryKanbanRepository,
)

pytestmark = pytest.mark.unit


def test_use_cases_create_and_list_boards() -> None:
    use_cases = KanbanUseCases(repository=InMemoryKanbanRepository())
    created = use_cases.create_board("Sprint")
    assert created.title == "Sprint"
    listed = use_cases.list_boards()
    assert [board.id for board in listed] == [created.id]


def test_use_cases_board_lookup_returns_err_for_missing_board() -> None:
    use_cases = KanbanUseCases(repository=InMemoryKanbanRepository())
    result = use_cases.get_board("00000000-0000-4000-8000-000000000001")
    assert isinstance(result, Err)


def test_use_cases_create_and_patch_card() -> None:
    use_cases = KanbanUseCases(repository=InMemoryKanbanRepository())
    board = use_cases.create_board("Board")
    column_result = use_cases.create_column(board.id, "Todo")
    assert isinstance(column_result, Ok)
    card_result = use_cases.create_card(
        column_result.value.id,
        "Task A",
        None,
        priority=CardPriority.MEDIUM,
        due_at=None,
    )
    assert isinstance(card_result, Ok)
    patched = use_cases.patch_card(card_result.value.id, title="Task B")
    assert isinstance(patched, Ok)
    assert patched.value.title == "Task B"
