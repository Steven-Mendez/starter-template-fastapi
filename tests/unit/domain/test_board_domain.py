from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.kanban.models import Board, Card, CardPriority, Column
from src.domain.shared.errors import KanbanError

pytestmark = pytest.mark.unit


def _make_board(board_id: str = "b1", num_columns: int = 0) -> Board:
    board = Board(id=board_id, title="Project Board", created_at=datetime.now(UTC))
    for index in range(num_columns):
        board.columns.append(
            Column(
                id=f"col-{index + 1}",
                board_id=board_id,
                title=f"Column {index + 1}",
                position=index,
            )
        )
    return board


def _append_column(board: Board, title: str) -> Column:
    column = Column(
        id=f"col-{len(board.columns) + 1}",
        board_id=board.id,
        title=title,
        position=len(board.columns),
    )
    board.columns.append(column)
    return column


def _append_card(column: Column, title: str) -> Card:
    card = Card(
        id=f"card-{len(column.cards) + 1}",
        column_id=column.id,
        title=title,
        description=None,
        position=len(column.cards),
        priority=CardPriority.MEDIUM,
        due_at=None,
    )
    column.insert_card(card)
    return card


def test_get_column_returns_column_by_id() -> None:
    board = _make_board(num_columns=2)

    found = board.get_column("col-2")

    assert found is not None
    assert found.id == "col-2"


def test_get_column_returns_none_for_missing_id() -> None:
    board = _make_board(num_columns=1)

    found = board.get_column("missing")

    assert found is None


def test_delete_column_removes_column() -> None:
    board = _make_board(num_columns=2)

    error = board.delete_column("col-1")

    assert error is None
    assert [column.id for column in board.columns] == ["col-2"]


def test_delete_column_reindexes_remaining_columns() -> None:
    board = _make_board(num_columns=3)

    error = board.delete_column("col-2")

    assert error is None
    assert [column.id for column in board.columns] == ["col-1", "col-3"]
    assert [column.position for column in board.columns] == [0, 1]


def test_delete_missing_column_returns_error() -> None:
    board = _make_board(num_columns=1)

    error = board.delete_column("does-not-exist")

    assert error == KanbanError.COLUMN_NOT_FOUND


def test_move_card_cross_column_on_same_board() -> None:
    board = _make_board()
    source = _append_column(board, "Todo")
    target = _append_column(board, "Doing")
    card = _append_card(source, "Task")

    error = board.move_card(card.id, source.id, target.id, requested_position=None)

    assert error is None
    assert source.cards == []
    assert [c.id for c in target.cards] == [card.id]


def test_move_card_reorder_within_same_column() -> None:
    board = _make_board()
    column = _append_column(board, "Todo")
    first = _append_card(column, "First")
    second = _append_card(column, "Second")

    error = board.move_card(first.id, column.id, column.id, requested_position=1)

    assert error is None
    assert [card.id for card in column.cards] == [second.id, first.id]
    assert [card.position for card in column.cards] == [0, 1]


def test_move_card_missing_source_column_returns_error() -> None:
    board = _make_board()
    target = _append_column(board, "Done")

    error = board.move_card("card-1", "missing-source", target.id, requested_position=0)

    assert error == KanbanError.INVALID_CARD_MOVE


def test_move_card_missing_target_column_returns_error() -> None:
    board = _make_board()
    source = _append_column(board, "Todo")
    card = _append_card(source, "Task")

    error = board.move_card(
        card.id,
        source.id,
        "missing-target",
        requested_position=None,
    )

    assert error == KanbanError.INVALID_CARD_MOVE


def test_move_card_preserves_card_data() -> None:
    board = _make_board()
    source = _append_column(board, "Todo")
    target = _append_column(board, "Done")
    due_at = datetime(2030, 1, 1, tzinfo=UTC)
    card = Card(
        id="task-42",
        column_id=source.id,
        title="Keep metadata",
        description="must persist",
        position=0,
        priority=CardPriority.HIGH,
        due_at=due_at,
    )
    source.insert_card(card)

    error = board.move_card(card.id, source.id, target.id, requested_position=None)

    assert error is None
    assert len(target.cards) == 1
    moved = target.cards[0]
    assert moved.id == "task-42"
    assert moved.title == "Keep metadata"
    assert moved.priority == CardPriority.HIGH
    assert moved.due_at == due_at
    assert moved.description == "must persist"
