from __future__ import annotations

import pytest

from src.application.queries import GetBoardQuery
from src.application.shared import AppOk
from tests.support.kanban_builders import HandlerHarness

pytestmark = pytest.mark.unit


def test_command_handlers_only_expose_mutations(
    handler_harness: HandlerHarness,
) -> None:
    commands = handler_harness.commands
    assert hasattr(commands, "handle_create_board")
    assert hasattr(commands, "handle_patch_card")
    assert not hasattr(commands, "handle_get_board")
    assert not hasattr(commands, "handle_list_boards")


def test_query_handlers_only_expose_reads(handler_harness: HandlerHarness) -> None:
    queries = handler_harness.queries
    assert hasattr(queries, "handle_list_boards")
    assert hasattr(queries, "handle_get_card")
    assert not hasattr(queries, "handle_create_board")
    assert not hasattr(queries, "handle_patch_card")


def test_router_use_case_can_be_done_with_split_handlers(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Roadmap")
    created_column = handler_harness.column(board.id, "Todo")
    created_card = handler_harness.card(created_column.id, "Task A")

    fetched_board = handler_harness.queries.handle_get_board(
        GetBoardQuery(board_id=board.id)
    )
    assert isinstance(fetched_board, AppOk)
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
