from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.application.commands import DeleteColumnCommand, PatchCardCommand
from src.application.contracts import AppCardPriority
from src.application.queries import GetBoardQuery
from src.application.shared import AppErr, ApplicationError, AppOk
from tests.support.kanban_builders import HandlerHarness

pytestmark = pytest.mark.unit

_UNKNOWN_COLUMN_ID = "00000000-0000-4000-8000-000000000099"


def test_create_entities_use_fake_id_generator(handler_harness: HandlerHarness) -> None:
    board = handler_harness.board("One")
    column = handler_harness.column(board.id, "c")
    card = handler_harness.card(column.id, "task")

    assert board.id == "00000000-0000-4000-8000-000000000001"
    assert column.id == "00000000-0000-4000-8000-000000000002"
    assert card.id == "00000000-0000-4000-8000-000000000003"


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

    assert isinstance(result, AppErr)
    assert result.error is ApplicationError.INVALID_CARD_MOVE


def test_move_card_fails_when_target_column_does_not_exist(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Targets")
    column = handler_harness.column(board.id, "c")
    card = handler_harness.card(column.id, "c")

    result = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, column_id=_UNKNOWN_COLUMN_ID)
    )

    assert isinstance(result, AppErr)
    assert result.error is ApplicationError.INVALID_CARD_MOVE


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

    assert isinstance(moved, AppOk)
    assert moved.value.column_id == col_b.id

    detail = handler_harness.queries.handle_get_board(GetBoardQuery(board_id=board.id))
    assert isinstance(detail, AppOk)
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

    assert isinstance(reordered, AppOk)

    detail = handler_harness.queries.handle_get_board(GetBoardQuery(board_id=board.id))
    assert isinstance(detail, AppOk)
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
    card = handler_harness.card(col_a.id, "move", priority=AppCardPriority.HIGH)

    moved = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, column_id=col_b.id)
    )

    assert isinstance(moved, AppOk)
    assert moved.value.priority is AppCardPriority.HIGH


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

    assert isinstance(moved, AppOk)
    assert moved.value.due_at == due_at


def test_patch_card_clear_due_at_when_clear_due_at_is_true(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Due clear")
    column = handler_harness.column(board.id, "A")
    due_at = datetime(2030, 1, 1, 0, 0, tzinfo=timezone.utc)
    card = handler_harness.card(column.id, "task", due_at=due_at)

    cleared = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, clear_due_at=True)
    )

    assert isinstance(cleared, AppOk)
    assert cleared.value.due_at is None


def test_patch_card_keeps_due_at_when_updating_other_fields(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Due keep")
    column = handler_harness.column(board.id, "A")
    due_at = datetime(2032, 2, 2, 12, 0, tzinfo=timezone.utc)
    card = handler_harness.card(column.id, "task", due_at=due_at)

    patched = handler_harness.commands.handle_patch_card(
        PatchCardCommand(card_id=card.id, title="renamed")
    )

    assert isinstance(patched, AppOk)
    assert patched.value.due_at == due_at


def test_delete_middle_column_reindexes_remaining_columns(
    handler_harness: HandlerHarness,
) -> None:
    board = handler_harness.board("Delete column")
    first = handler_harness.column(board.id, "A")
    middle = handler_harness.column(board.id, "B")
    last = handler_harness.column(board.id, "C")

    deleted = handler_harness.commands.handle_delete_column(
        DeleteColumnCommand(column_id=middle.id)
    )
    assert isinstance(deleted, AppOk)

    detail = handler_harness.queries.handle_get_board(GetBoardQuery(board_id=board.id))
    assert isinstance(detail, AppOk)

    by_id = {column.id: column for column in detail.value.columns}
    assert middle.id not in by_id
    assert by_id[first.id].position == 0
    assert by_id[last.id].position == 1
