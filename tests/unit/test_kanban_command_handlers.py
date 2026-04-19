from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.commands import PatchCardCommand
from src.application.queries import GetBoardQuery
from src.domain.kanban.models import CardPriority
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok
from tests.support.kanban_builders import HandlerHarness

pytestmark = pytest.mark.unit

_UNKNOWN_COLUMN_ID = "00000000-0000-4000-8000-000000000099"


def test_card_cannot_move_to_column_on_another_board(
    handler_harness: HandlerHarness,
) -> None:
    board_a = handler_harness.board("One")
    board_b = handler_harness.board("Two")
    col_a = handler_harness.column(board_a.id, "x")
    col_b = handler_harness.column(board_b.id, "y")
    card = handler_harness.card(col_a.id, "c")

    result = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, column_id=col_b.id)
    )

    assert isinstance(result, Err)
    assert result.error is KanbanError.INVALID_CARD_MOVE


def test_move_card_fails_when_target_column_does_not_exist(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Targets")
    column = handler_harness.column(board.id, "c")
    card = handler_harness.card(column.id, "c")

    result = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, column_id=_UNKNOWN_COLUMN_ID)
    )

    assert isinstance(result, Err)
    assert result.error is KanbanError.INVALID_CARD_MOVE


def test_card_can_move_between_columns_on_same_board(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Move")
    col_a = handler_harness.column(board.id, "A")
    col_b = handler_harness.column(board.id, "B")
    card = handler_harness.card(col_a.id, "Move me")

    moved = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, column_id=col_b.id)
    )

    assert isinstance(moved, Ok)
    assert moved.value.column_id == col_b.id

    detail = handler_harness.queries.handle_get_board(GetBoardQuery(board_id=board.id))
    assert isinstance(detail, Ok)
    by_title = {column.title: column for column in detail.value.columns}
    assert len(by_title["A"].cards) == 0
    assert len(by_title["B"].cards) == 1


def test_card_order_within_column_follows_position_updates(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Reorder")
    column = handler_harness.column(board.id, "c")
    card_a = handler_harness.card(column.id, "a")
    handler_harness.card(column.id, "b")

    reordered = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card_a.id, position=1)
    )

    assert isinstance(reordered, Ok)

    detail = handler_harness.queries.handle_get_board(GetBoardQuery(board_id=board.id))
    assert isinstance(detail, Ok)
    detail_column = next(
        (candidate for candidate in detail.value.columns if candidate.id == column.id),
        None,
    )
    assert detail_column is not None
    assert [card.title for card in detail_column.cards] == ["b", "a"]


def test_priority_preserved_when_moving_between_columns(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Prio")
    col_a = handler_harness.column(board.id, "A")
    col_b = handler_harness.column(board.id, "B")
    card = handler_harness.card(col_a.id, "move", priority=CardPriority.HIGH)

    moved = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, column_id=col_b.id)
    )

    assert isinstance(moved, Ok)
    assert moved.value.priority is CardPriority.HIGH


def test_due_at_preserved_when_moving_between_columns(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Due")
    col_a = handler_harness.column(board.id, "A")
    col_b = handler_harness.column(board.id, "B")
    due_at = datetime(2034, 5, 5, 8, 0, tzinfo=timezone.utc)
    card = handler_harness.card(col_a.id, "move", due_at=due_at)

    moved = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, column_id=col_b.id)
    )

    assert isinstance(moved, Ok)
    assert moved.value.due_at == due_at
