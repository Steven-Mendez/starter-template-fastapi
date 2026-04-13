from __future__ import annotations

import pytest

from kanban.store import KanbanStore

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


def test_find_board_returns_none_when_id_unknown(kanban_store: KanbanStore) -> None:
    assert kanban_store.get_board(_UNKNOWN_BOARD_ID) is None


def test_board_title_can_be_changed_and_board_can_be_removed(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Original")
    updated = kanban_store.update_board(board.id, "Renamed")
    assert updated is not None
    assert updated.title == "Renamed"
    detail = kanban_store.get_board(board.id)
    assert detail is not None
    assert detail.title == "Renamed"
    assert kanban_store.delete_board(board.id) is True
    assert kanban_store.get_board(board.id) is None


def test_removing_board_removes_nested_columns_and_cards(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("With children")
    column = kanban_store.create_column(board.id, "Column")
    assert column is not None
    card = kanban_store.create_card(column.id, "x", None)
    assert card is not None
    assert kanban_store.delete_board(board.id) is True
    assert kanban_store.get_card(card.id) is None


def test_board_detail_lists_columns_in_creation_order(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Ordered")
    first = kanban_store.create_column(board.id, "Todo")
    second = kanban_store.create_column(board.id, "Done")
    assert first is not None and second is not None
    assert first.position == 0 and second.position == 1
    detail = kanban_store.get_board(board.id)
    assert detail is not None
    assert [column.title for column in detail.columns] == ["Todo", "Done"]


def test_card_is_nested_under_column_in_board_detail(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Nested")
    column = kanban_store.create_column(board.id, "Doing")
    assert column is not None
    card = kanban_store.create_card(column.id, "Task A", "Note")
    assert card is not None
    assert card.column_id == column.id
    assert card.position == 0
    detail = kanban_store.get_board(board.id)
    assert detail is not None
    assert detail.columns[0].cards[0].id == card.id


def test_create_column_fails_when_board_does_not_exist(kanban_store: KanbanStore) -> None:
    assert kanban_store.create_column(_UNKNOWN_BOARD_ID, "Orphan") is None


def test_create_card_fails_when_column_does_not_exist(kanban_store: KanbanStore) -> None:
    assert kanban_store.create_card(_UNKNOWN_COLUMN_ID, "Orphan", None) is None


def test_card_can_move_between_columns_on_same_board(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Move")
    column_a = kanban_store.create_column(board.id, "A")
    column_b = kanban_store.create_column(board.id, "B")
    assert column_a is not None and column_b is not None
    card = kanban_store.create_card(column_a.id, "Move me", None)
    assert card is not None
    moved = kanban_store.update_card(card.id, column_id=column_b.id)
    assert moved is not None
    assert moved.column_id == column_b.id
    detail = kanban_store.get_board(board.id)
    assert detail is not None
    columns_by_title = {column.title: column for column in detail.columns}
    assert len(columns_by_title["A"].cards) == 0
    assert len(columns_by_title["B"].cards) == 1


def test_card_cannot_move_to_column_on_another_board(kanban_store: KanbanStore) -> None:
    first_board = kanban_store.create_board("One")
    second_board = kanban_store.create_board("Two")
    column_on_first = kanban_store.create_column(first_board.id, "x")
    column_on_second = kanban_store.create_column(second_board.id, "y")
    assert column_on_first is not None and column_on_second is not None
    card = kanban_store.create_card(column_on_first.id, "c", None)
    assert card is not None
    assert kanban_store.update_card(card.id, column_id=column_on_second.id) is None


def test_move_card_fails_when_target_column_does_not_exist(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Targets")
    column = kanban_store.create_column(board.id, "c")
    assert column is not None
    card = kanban_store.create_card(column.id, "c", None)
    assert card is not None
    assert (
        kanban_store.update_card(card.id, column_id=_UNKNOWN_ENTITY_ID) is None
    )


def test_card_order_within_column_follows_position_updates(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Reorder")
    column = kanban_store.create_column(board.id, "c")
    assert column is not None
    first_card = kanban_store.create_card(column.id, "a", None)
    second_card = kanban_store.create_card(column.id, "b", None)
    assert first_card is not None and second_card is not None
    reordered = kanban_store.update_card(first_card.id, position=1)
    assert reordered is not None
    detail = kanban_store.get_board(board.id)
    assert detail is not None
    titles = [card.title for card in detail.columns[0].cards]
    assert titles == ["b", "a"]


def test_removing_column_removes_attached_cards(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Cascade")
    column = kanban_store.create_column(board.id, "X")
    assert column is not None
    card = kanban_store.create_card(column.id, "Gone", None)
    assert card is not None
    assert kanban_store.delete_column(column.id) is True
    assert kanban_store.get_card(card.id) is None


def test_find_card_returns_none_when_id_unknown(kanban_store: KanbanStore) -> None:
    assert kanban_store.get_card(_UNKNOWN_ENTITY_ID) is None


def test_card_title_can_update_without_touching_description(kanban_store: KanbanStore) -> None:
    board = kanban_store.create_board("Fields")
    column = kanban_store.create_column(board.id, "c")
    assert column is not None
    card = kanban_store.create_card(column.id, "old", "d")
    assert card is not None
    updated = kanban_store.update_card(card.id, title="new")
    assert updated is not None
    assert updated.title == "new"
    assert updated.description == "d"
