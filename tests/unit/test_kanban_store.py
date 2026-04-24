from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import cast

import pytest

from src.domain.kanban.models import Board, Card, CardPriority, Column
from src.domain.kanban.repository import KanbanRepositoryPort as KanbanStore
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok, Result
from tests.support.kanban_builders import StoreBuilder

pytestmark = pytest.mark.unit

_UNKNOWN_BOARD_ID = "00000000-0000-4000-8000-000000000001"
_UNKNOWN_COLUMN_ID = "00000000-0000-4000-8000-000000000002"
_UNKNOWN_ENTITY_ID = "00000000-0000-4000-8000-000000000099"
_DUE_AT_UNSET = object()


def _find_card(board: Board, card_id: str) -> Card | None:
    for column in board.columns:
        for card in column.cards:
            if card.id == card_id:
                return card
    return None


def _require_card(board: Board, card_id: str) -> Card:
    card = _find_card(board, card_id)
    assert card is not None
    return card


def _get_card_result(
    kanban_store: KanbanStore,
    card_id: str,
) -> Result[Card, KanbanError]:
    board_id = kanban_store.find_board_id_by_card(card_id)
    if board_id is None:
        return Err(KanbanError.CARD_NOT_FOUND)

    board_result = kanban_store.get_board(board_id)
    if isinstance(board_result, Err):
        return board_result

    card = _find_card(board_result.value, card_id)
    if card is None:
        return Err(KanbanError.CARD_NOT_FOUND)
    return Ok(card)


def _create_column_result(
    kanban_store: KanbanStore,
    board_id: str,
    title: str,
) -> Result[Column, KanbanError]:
    board_result = kanban_store.get_board(board_id)
    if isinstance(board_result, Err):
        return Err(board_result.error)

    board = board_result.value
    column = Column(
        id=str(uuid.uuid4()),
        board_id=board_id,
        title=title,
        position=max((candidate.position for candidate in board.columns), default=-1)
        + 1,
        cards=[],
    )
    board.columns.append(column)
    save_result = kanban_store.save_board(board)
    if isinstance(save_result, Err):
        return save_result
    return Ok(column)


def _create_card_result(
    kanban_store: KanbanStore,
    column_id: str,
    title: str,
    description: str | None,
    *,
    priority: CardPriority = CardPriority.MEDIUM,
    due_at: datetime | None = None,
) -> Result[Card, KanbanError]:
    board_id = kanban_store.find_board_id_by_column(column_id)
    if board_id is None:
        return Err(KanbanError.COLUMN_NOT_FOUND)

    board_result = kanban_store.get_board(board_id)
    if isinstance(board_result, Err):
        return board_result
    board = board_result.value

    column = next(
        (candidate for candidate in board.columns if candidate.id == column_id), None
    )
    if column is None:
        return Err(KanbanError.COLUMN_NOT_FOUND)

    card = Card(
        id=str(uuid.uuid4()),
        column_id=column_id,
        title=title,
        description=description,
        position=0,
        priority=priority,
        due_at=due_at,
    )
    column.insert_card(card)
    save_result = kanban_store.save_board(board)
    if isinstance(save_result, Err):
        return save_result
    return Ok(card)


def _delete_column_result(
    kanban_store: KanbanStore,
    column_id: str,
) -> Result[None, KanbanError]:
    board_id = kanban_store.find_board_id_by_column(column_id)
    if board_id is None:
        return Err(KanbanError.COLUMN_NOT_FOUND)

    board_result = kanban_store.get_board(board_id)
    if isinstance(board_result, Err):
        return board_result
    board = board_result.value

    delete_error = board.delete_column(column_id)
    if delete_error is not None:
        return Err(delete_error)

    save_result = kanban_store.save_board(board)
    if isinstance(save_result, Err):
        return save_result
    return Ok(None)


def _update_card(
    kanban_store: KanbanStore,
    card_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    priority: CardPriority | None = None,
    due_at: datetime | None | object = _DUE_AT_UNSET,
) -> Result[Card, KanbanError]:
    board_id = kanban_store.find_board_id_by_card(card_id)
    if board_id is None:
        return Err(KanbanError.CARD_NOT_FOUND)

    board_result = kanban_store.get_board(board_id)
    if isinstance(board_result, Err):
        return board_result
    board = board_result.value

    card = _find_card(board, card_id)
    if card is None:
        return Err(KanbanError.CARD_NOT_FOUND)

    if title is not None:
        card.title = title
    if description is not None:
        card.description = description
    if priority is not None:
        card.priority = priority
    if due_at is not _DUE_AT_UNSET:
        card.due_at = cast(datetime | None, due_at)

    save_result = kanban_store.save_board(board)
    if isinstance(save_result, Err):
        return save_result
    return Ok(card)


def test_list_boards_includes_newly_created_board(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    created = store_builder.board("Sprint")
    assert created.title == "Sprint"
    assert created.id
    listed = kanban_store.list_boards()
    assert {board.id for board in listed} == {created.id}


def test_find_board_returns_err_when_id_unknown(kanban_store: KanbanStore) -> None:
    result = kanban_store.get_board(_UNKNOWN_BOARD_ID)
    assert isinstance(result, Err)
    assert result.error is KanbanError.BOARD_NOT_FOUND


def test_board_title_can_be_changed_and_board_can_be_removed(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Original")
    updated = kanban_store.update_board(board.id, "Renamed")
    assert isinstance(updated, Ok)
    assert updated.value.title == "Renamed"

    detail_result = kanban_store.get_board(board.id)
    assert isinstance(detail_result, Ok)
    assert detail_result.value.title == "Renamed"

    assert isinstance(kanban_store.delete_board(board.id), Ok)
    missing = kanban_store.get_board(board.id)
    assert isinstance(missing, Err)
    assert missing.error is KanbanError.BOARD_NOT_FOUND


def test_removing_board_removes_nested_columns_and_cards(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("With children")
    column = store_builder.column(board.id, "Column")
    card = store_builder.card(column.id, "x")

    assert isinstance(kanban_store.delete_board(board.id), Ok)
    assert isinstance(_get_card_result(kanban_store, card.id), Err)


def test_board_detail_lists_columns_in_creation_order(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Ordered")
    first = store_builder.column(board.id, "Todo")
    second = store_builder.column(board.id, "Done")
    assert first.position == 0 and second.position == 1

    detail_result = kanban_store.get_board(board.id)
    assert isinstance(detail_result, Ok)
    assert [column.title for column in detail_result.value.columns] == ["Todo", "Done"]


def test_card_is_nested_under_column_in_board_detail(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Nested")
    column = store_builder.column(board.id, "Doing")
    card = store_builder.card(column.id, "Task A", "Note")
    assert card.column_id == column.id
    assert card.position == 0

    detail_result = kanban_store.get_board(board.id)
    assert isinstance(detail_result, Ok)
    nested = _require_card(detail_result.value, card.id)
    assert nested.id == card.id


def test_create_column_fails_when_board_does_not_exist(
    kanban_store: KanbanStore,
) -> None:
    result = _create_column_result(kanban_store, _UNKNOWN_BOARD_ID, "Orphan")
    assert isinstance(result, Err)
    assert result.error is KanbanError.BOARD_NOT_FOUND


def test_create_card_fails_when_column_does_not_exist(
    kanban_store: KanbanStore,
) -> None:
    result = _create_card_result(kanban_store, _UNKNOWN_COLUMN_ID, "Orphan", None)
    assert isinstance(result, Err)
    assert result.error is KanbanError.COLUMN_NOT_FOUND


def test_removing_column_removes_attached_cards(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Cascade")
    column = store_builder.column(board.id, "X")
    card = store_builder.card(column.id, "Gone")

    assert isinstance(_delete_column_result(kanban_store, column.id), Ok)
    assert isinstance(_get_card_result(kanban_store, card.id), Err)


def test_deleting_middle_column_keeps_contiguous_positions(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Columns")
    first = store_builder.column(board.id, "A")
    middle = store_builder.column(board.id, "B")
    last = store_builder.column(board.id, "C")

    assert isinstance(_delete_column_result(kanban_store, middle.id), Ok)

    board_result = kanban_store.get_board(board.id)
    assert isinstance(board_result, Ok)
    columns_by_id = {column.id: column for column in board_result.value.columns}
    assert middle.id not in columns_by_id
    assert columns_by_id[first.id].position == 0
    assert columns_by_id[last.id].position == 1


def test_find_card_returns_err_when_id_unknown(kanban_store: KanbanStore) -> None:
    result = _get_card_result(kanban_store, _UNKNOWN_ENTITY_ID)
    assert isinstance(result, Err)
    assert result.error is KanbanError.CARD_NOT_FOUND


def test_create_card_default_and_explicit_priority(
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Prio")
    column = store_builder.column(board.id, "c")
    default_priority = store_builder.card(column.id, "d")
    assert default_priority.priority is CardPriority.MEDIUM

    high = store_builder.card(column.id, "h", priority=CardPriority.HIGH)
    low = store_builder.card(column.id, "l", priority=CardPriority.LOW)
    assert high.priority is CardPriority.HIGH
    assert low.priority is CardPriority.LOW


def test_board_detail_includes_card_priority(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Prio")
    column = store_builder.column(board.id, "c")
    card = store_builder.card(column.id, "a", priority=CardPriority.HIGH)

    detail_result = kanban_store.get_board(board.id)
    assert isinstance(detail_result, Ok)
    nested = _require_card(detail_result.value, card.id)
    assert nested.priority is CardPriority.HIGH


def test_update_card_changes_priority(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Prio")
    column = store_builder.column(board.id, "c")
    card = store_builder.card(column.id, "x")

    updated = _update_card(kanban_store, card.id, priority=CardPriority.LOW)
    assert isinstance(updated, Ok)
    assert updated.value.priority is CardPriority.LOW


def test_card_title_can_update_without_touching_description(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Fields")
    column = store_builder.column(board.id, "c")
    card = store_builder.card(column.id, "old", "d")

    updated = _update_card(kanban_store, card.id, title="new")
    assert isinstance(updated, Ok)
    assert updated.value.title == "new"
    assert updated.value.description == "d"


def test_create_card_default_and_explicit_due_at(
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Due")
    column = store_builder.column(board.id, "c")
    default_due_at = store_builder.card(column.id, "d")
    assert default_due_at.due_at is None

    due_at = datetime(2030, 6, 1, 9, 30, tzinfo=timezone.utc)
    scheduled = store_builder.card(column.id, "s", due_at=due_at)
    assert scheduled.due_at == due_at


def test_update_card_sets_and_clears_due_at(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Due")
    column = store_builder.column(board.id, "c")
    card = store_builder.card(column.id, "x")

    due_at = datetime(2031, 2, 2, 0, 0, tzinfo=timezone.utc)
    updated = _update_card(kanban_store, card.id, due_at=due_at)
    assert isinstance(updated, Ok)
    assert updated.value.due_at == due_at

    cleared = _update_card(kanban_store, card.id, due_at=None)
    assert isinstance(cleared, Ok)
    assert cleared.value.due_at is None


def test_omit_due_at_on_update_preserves_value(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Due")
    column = store_builder.column(board.id, "c")
    card = store_builder.card(column.id, "x")

    due_at = datetime(2032, 3, 3, 15, 0, tzinfo=timezone.utc)
    first = _update_card(kanban_store, card.id, due_at=due_at)
    assert isinstance(first, Ok)

    same = _update_card(kanban_store, card.id, title="renamed", due_at=_DUE_AT_UNSET)
    assert isinstance(same, Ok)
    assert same.value.title == "renamed"
    assert same.value.due_at == due_at


def test_board_detail_includes_due_at_on_cards(
    kanban_store: KanbanStore,
    store_builder: StoreBuilder,
) -> None:
    board = store_builder.board("Due")
    column = store_builder.column(board.id, "c")
    due_at = datetime(2033, 4, 4, 12, 0, tzinfo=timezone.utc)
    card = store_builder.card(column.id, "a", due_at=due_at)

    detail_result = kanban_store.get_board(board.id)
    assert isinstance(detail_result, Ok)
    nested = _require_card(detail_result.value, card.id)
    assert nested.due_at == due_at
