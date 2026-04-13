from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kanban.errors import KanbanError
from kanban.result import Err, Ok
from kanban.schemas import CardPriority
from kanban.store import DUE_AT_UNSET, KanbanStore

pytestmark = pytest.mark.unit

_UNKNOWN_BOARD_ID = "00000000-0000-4000-8000-000000000001"
_UNKNOWN_COLUMN_ID = "00000000-0000-4000-8000-000000000002"
_UNKNOWN_ENTITY_ID = "00000000-0000-4000-8000-000000000099"


def test_list_boards_includes_newly_created_board(kanban_store: KanbanStore) -> None:
    created = kanban_store.create_board("Sprint")
    assert created.title == "Sprint"
    assert created.id
    listed = kanban_store.list_boards()
    assert len(listed) == 1
    assert listed[0].id == created.id


def test_find_board_returns_err_when_id_unknown(kanban_store: KanbanStore) -> None:
    r = kanban_store.get_board(_UNKNOWN_BOARD_ID)
    assert isinstance(r, Err)
    assert r.error is KanbanError.BOARD_NOT_FOUND


def test_board_title_can_be_changed_and_board_can_be_removed(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Original")
    updated = kanban_store.update_board(board.id, "Renamed")
    assert isinstance(updated, Ok)
    assert updated.value.title == "Renamed"
    detail_r = kanban_store.get_board(board.id)
    assert isinstance(detail_r, Ok)
    assert detail_r.value.title == "Renamed"
    assert isinstance(kanban_store.delete_board(board.id), Ok)
    missing = kanban_store.get_board(board.id)
    assert isinstance(missing, Err)
    assert missing.error is KanbanError.BOARD_NOT_FOUND


def test_removing_board_removes_nested_columns_and_cards(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("With children")
    column = kanban_store.create_column(board.id, "Column")
    assert isinstance(column, Ok)
    card = kanban_store.create_card(column.value.id, "x", None)
    assert isinstance(card, Ok)
    assert isinstance(kanban_store.delete_board(board.id), Ok)
    gone = kanban_store.get_card(card.value.id)
    assert isinstance(gone, Err)


def test_board_detail_lists_columns_in_creation_order(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Ordered")
    first = kanban_store.create_column(board.id, "Todo")
    second = kanban_store.create_column(board.id, "Done")
    assert isinstance(first, Ok) and isinstance(second, Ok)
    assert first.value.position == 0 and second.value.position == 1
    detail_r = kanban_store.get_board(board.id)
    assert isinstance(detail_r, Ok)
    assert [column.title for column in detail_r.value.columns] == ["Todo", "Done"]


def test_card_is_nested_under_column_in_board_detail(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Nested")
    column = kanban_store.create_column(board.id, "Doing")
    assert isinstance(column, Ok)
    card = kanban_store.create_card(column.value.id, "Task A", "Note")
    assert isinstance(card, Ok)
    assert card.value.column_id == column.value.id
    assert card.value.position == 0
    detail_r = kanban_store.get_board(board.id)
    assert isinstance(detail_r, Ok)
    assert detail_r.value.columns[0].cards[0].id == card.value.id


def test_create_column_fails_when_board_does_not_exist(kanban_store: KanbanStore) -> None:
    r = kanban_store.create_column(_UNKNOWN_BOARD_ID, "Orphan")
    assert isinstance(r, Err)
    assert r.error is KanbanError.BOARD_NOT_FOUND


def test_create_card_fails_when_column_does_not_exist(kanban_store: KanbanStore) -> None:
    r = kanban_store.create_card(_UNKNOWN_COLUMN_ID, "Orphan", None)
    assert isinstance(r, Err)
    assert r.error is KanbanError.COLUMN_NOT_FOUND


def test_card_can_move_between_columns_on_same_board(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Move")
    column_a = kanban_store.create_column(board.id, "A")
    column_b = kanban_store.create_column(board.id, "B")
    assert isinstance(column_a, Ok) and isinstance(column_b, Ok)
    card = kanban_store.create_card(column_a.value.id, "Move me", None)
    assert isinstance(card, Ok)
    moved = kanban_store.update_card(card.value.id, column_id=column_b.value.id)
    assert isinstance(moved, Ok)
    assert moved.value.column_id == column_b.value.id
    detail_r = kanban_store.get_board(board.id)
    assert isinstance(detail_r, Ok)
    columns_by_title = {column.title: column for column in detail_r.value.columns}
    assert len(columns_by_title["A"].cards) == 0
    assert len(columns_by_title["B"].cards) == 1


def test_card_cannot_move_to_column_on_another_board(kanban_store: KanbanStore) -> None:
    first_board = kanban_store.create_board("One")
    second_board = kanban_store.create_board("Two")
    column_on_first = kanban_store.create_column(first_board.id, "x")
    column_on_second = kanban_store.create_column(second_board.id, "y")
    assert isinstance(column_on_first, Ok) and isinstance(column_on_second, Ok)
    card = kanban_store.create_card(column_on_first.value.id, "c", None)
    assert isinstance(card, Ok)
    r = kanban_store.update_card(card.value.id, column_id=column_on_second.value.id)
    assert isinstance(r, Err)
    assert r.error is KanbanError.INVALID_CARD_MOVE


def test_move_card_fails_when_target_column_does_not_exist(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Targets")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    card = kanban_store.create_card(column.value.id, "c", None)
    assert isinstance(card, Ok)
    r = kanban_store.update_card(card.value.id, column_id=_UNKNOWN_ENTITY_ID)
    assert isinstance(r, Err)
    assert r.error is KanbanError.COLUMN_NOT_FOUND


def test_card_order_within_column_follows_position_updates(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Reorder")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    first_card = kanban_store.create_card(column.value.id, "a", None)
    second_card = kanban_store.create_card(column.value.id, "b", None)
    assert isinstance(first_card, Ok) and isinstance(second_card, Ok)
    reordered = kanban_store.update_card(first_card.value.id, position=1)
    assert isinstance(reordered, Ok)
    detail_r = kanban_store.get_board(board.id)
    assert isinstance(detail_r, Ok)
    titles = [card.title for card in detail_r.value.columns[0].cards]
    assert titles == ["b", "a"]


def test_removing_column_removes_attached_cards(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Cascade")
    column = kanban_store.create_column(board.id, "X")
    assert isinstance(column, Ok)
    card = kanban_store.create_card(column.value.id, "Gone", None)
    assert isinstance(card, Ok)
    assert isinstance(kanban_store.delete_column(column.value.id), Ok)
    assert isinstance(kanban_store.get_card(card.value.id), Err)


def test_find_card_returns_err_when_id_unknown(kanban_store: KanbanStore) -> None:
    r = kanban_store.get_card(_UNKNOWN_ENTITY_ID)
    assert isinstance(r, Err)
    assert r.error is KanbanError.CARD_NOT_FOUND


def test_create_card_default_and_explicit_priority(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Prio")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    default_p = kanban_store.create_card(column.value.id, "d", None)
    assert isinstance(default_p, Ok)
    assert default_p.value.priority is CardPriority.MEDIUM
    high = kanban_store.create_card(
        column.value.id, "h", None, priority=CardPriority.HIGH
    )
    low = kanban_store.create_card(column.value.id, "l", None, priority=CardPriority.LOW)
    assert isinstance(high, Ok) and isinstance(low, Ok)
    assert high.value.priority is CardPriority.HIGH
    assert low.value.priority is CardPriority.LOW


def test_board_detail_includes_card_priority(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Prio")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    kanban_store.create_card(column.value.id, "a", None, priority=CardPriority.HIGH)
    detail_r = kanban_store.get_board(board.id)
    assert isinstance(detail_r, Ok)
    assert detail_r.value.columns[0].cards[0].priority is CardPriority.HIGH


def test_update_card_changes_priority(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Prio")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    card = kanban_store.create_card(column.value.id, "x", None)
    assert isinstance(card, Ok)
    updated = kanban_store.update_card(card.value.id, priority=CardPriority.LOW)
    assert isinstance(updated, Ok)
    assert updated.value.priority is CardPriority.LOW


def test_priority_preserved_when_moving_between_columns(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Prio")
    col_a = kanban_store.create_column(board.id, "A")
    col_b = kanban_store.create_column(board.id, "B")
    assert isinstance(col_a, Ok) and isinstance(col_b, Ok)
    card = kanban_store.create_card(
        col_a.value.id, "move", None, priority=CardPriority.HIGH
    )
    assert isinstance(card, Ok)
    moved = kanban_store.update_card(card.value.id, column_id=col_b.value.id)
    assert isinstance(moved, Ok)
    assert moved.value.priority is CardPriority.HIGH


def test_card_title_can_update_without_touching_description(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Fields")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    card = kanban_store.create_card(column.value.id, "old", "d")
    assert isinstance(card, Ok)
    updated = kanban_store.update_card(card.value.id, title="new")
    assert isinstance(updated, Ok)
    assert updated.value.title == "new"
    assert updated.value.description == "d"


def test_create_card_default_and_explicit_due_at(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Due")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    default_d = kanban_store.create_card(column.value.id, "d", None)
    assert isinstance(default_d, Ok)
    assert default_d.value.due_at is None
    when = datetime(2030, 6, 1, 9, 30, tzinfo=timezone.utc)
    scheduled = kanban_store.create_card(column.value.id, "s", None, due_at=when)
    assert isinstance(scheduled, Ok)
    assert scheduled.value.due_at == when


def test_update_card_sets_and_clears_due_at(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Due")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    card = kanban_store.create_card(column.value.id, "x", None)
    assert isinstance(card, Ok)
    when = datetime(2031, 2, 2, 0, 0, tzinfo=timezone.utc)
    updated = kanban_store.update_card(card.value.id, due_at=when)
    assert isinstance(updated, Ok)
    assert updated.value.due_at == when
    cleared = kanban_store.update_card(card.value.id, due_at=None)
    assert isinstance(cleared, Ok)
    assert cleared.value.due_at is None


def test_omit_due_at_on_update_preserves_value(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Due")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    card = kanban_store.create_card(column.value.id, "x", None)
    assert isinstance(card, Ok)
    when = datetime(2032, 3, 3, 15, 0, tzinfo=timezone.utc)
    kanban_store.update_card(card.value.id, due_at=when)
    same = kanban_store.update_card(card.value.id, title="renamed", due_at=DUE_AT_UNSET)
    assert isinstance(same, Ok)
    assert same.value.title == "renamed"
    assert same.value.due_at == when


def test_board_detail_includes_due_at_on_cards(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Due")
    column = kanban_store.create_column(board.id, "c")
    assert isinstance(column, Ok)
    when = datetime(2033, 4, 4, 12, 0, tzinfo=timezone.utc)
    kanban_store.create_card(column.value.id, "a", None, due_at=when)
    detail_r = kanban_store.get_board(board.id)
    assert isinstance(detail_r, Ok)
    assert detail_r.value.columns[0].cards[0].due_at == when


def test_due_at_preserved_when_moving_between_columns(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Due")
    col_a = kanban_store.create_column(board.id, "A")
    col_b = kanban_store.create_column(board.id, "B")
    assert isinstance(col_a, Ok) and isinstance(col_b, Ok)
    when = datetime(2034, 5, 5, 8, 0, tzinfo=timezone.utc)
    card = kanban_store.create_card(col_a.value.id, "move", None, due_at=when)
    assert isinstance(card, Ok)
    moved = kanban_store.update_card(card.value.id, column_id=col_b.value.id)
    assert isinstance(moved, Ok)
    assert moved.value.due_at == when
