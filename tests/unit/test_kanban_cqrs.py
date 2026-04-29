from __future__ import annotations

import pytest

from src.domain.shared.result import Ok
from tests.support.kanban_builders import HandlerHarness

pytestmark = pytest.mark.unit


def test_command_use_cases_expose_execute(
    handler_harness: HandlerHarness,
) -> None:
    assert hasattr(handler_harness.create_column_use_case, "execute")
    assert hasattr(handler_harness.patch_card_use_case, "execute")
    assert hasattr(handler_harness.delete_board_use_case, "execute")


def test_query_use_cases_expose_execute(handler_harness: HandlerHarness) -> None:
    assert hasattr(handler_harness.get_board_use_case, "execute")
    assert hasattr(handler_harness.get_card_use_case, "execute")
    assert hasattr(handler_harness.check_readiness_use_case, "execute")


def test_query_repository_view_hides_write_methods(
    handler_harness: HandlerHarness,
) -> None:
    repository = handler_harness.get_board_use_case.query_repository
    assert hasattr(repository, "list_all")
    assert hasattr(repository, "find_by_id")
    assert not hasattr(repository, "save")
    assert not hasattr(repository, "remove")
    assert not hasattr(repository, "find_board_id_by_column")


def test_router_use_case_can_be_done_with_split_handlers(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Roadmap")
    created_column = handler_harness.column(board.id, "Todo")
    created_card = handler_harness.card(created_column.id, "Task A")

    fetched_board = handler_harness.get_board(board.id)
    assert isinstance(fetched_board, Ok)
    todo_column = next(
        (
            column
            for column in fetched_board.value.columns
            if column.id == created_column.id
        ),
        None,
    )
    assert todo_column is not None
    assert {card.id for card in todo_column.cards} == {created_card.id}
