"""Unit tests for Kanban domain board behavior."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board, Card, CardPriority, Column
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _board() -> Board:
    return Board(id="b1", title="Roadmap", created_at=NOW)


def _column(board_id: str, column_id: str, position: int) -> Column:
    return Column(
        id=column_id, board_id=board_id, title=f"col-{column_id}", position=position
    )


def _card(card_id: str, column_id: str, position: int = 0) -> Card:
    return Card(
        id=card_id,
        column_id=column_id,
        title=f"card-{card_id}",
        description=None,
        position=position,
        priority=CardPriority.MEDIUM,
        due_at=None,
    )


class TestBoardColumns:
    def test_add_column_appends_in_order(self) -> None:
        board = _board()
        col1 = _column("b1", "c1", 0)
        col2 = _column("b1", "c2", 1)
        board.add_column(col1)
        board.add_column(col2)
        assert board.columns == [col1, col2]
        assert board.next_column_position() == 2

    def test_get_column_returns_match_or_none(self) -> None:
        board = _board()
        col = _column("b1", "c1", 0)
        board.add_column(col)
        assert board.get_column("c1") is col
        assert board.get_column("missing") is None

    def test_delete_column_recalculates_positions(self) -> None:
        board = _board()
        for i, cid in enumerate(["c1", "c2", "c3"]):
            board.add_column(_column("b1", cid, i))
        result = board.delete_column("c2")
        assert isinstance(result, Ok)
        assert [c.id for c in board.columns] == ["c1", "c3"]
        assert [c.position for c in board.columns] == [0, 1]

    def test_delete_column_missing_returns_err(self) -> None:
        board = _board()
        result = board.delete_column("missing")
        assert isinstance(result, Err)
        assert result.error == KanbanError.COLUMN_NOT_FOUND


class TestBoardFindCard:
    def test_find_column_containing_card_and_get_card(self) -> None:
        board = _board()
        col = _column("b1", "c1", 0)
        card = _card("k1", "c1")
        col.cards.append(card)
        board.add_column(col)
        assert board.find_column_containing_card("k1") is col
        assert board.get_card("k1") is card
        assert board.find_column_containing_card("absent") is None
        assert board.get_card("absent") is None


class TestBoardMoveCard:
    def _populated(self) -> Board:
        board = _board()
        col_a = _column("b1", "ca", 0)
        col_a.cards.append(_card("k1", "ca", 0))
        col_b = _column("b1", "cb", 1)
        board.add_column(col_a)
        board.add_column(col_b)
        return board

    def test_move_card_to_other_column_succeeds(self) -> None:
        board = self._populated()
        result = board.move_card("k1", "ca", "cb", requested_position=None)
        assert isinstance(result, Ok)
        col_a = board.get_column("ca")
        col_b = board.get_column("cb")
        assert col_a is not None and col_b is not None
        assert [c.id for c in col_a.cards] == []
        assert [c.id for c in col_b.cards] == ["k1"]

    def test_move_card_within_same_column_with_position(self) -> None:
        board = self._populated()
        col = board.get_column("ca")
        assert col is not None
        col.cards.append(_card("k2", "ca", 1))
        result = board.move_card("k1", "ca", "ca", requested_position=1)
        assert isinstance(result, Ok)
        assert [c.id for c in col.cards] == ["k2", "k1"]

    def test_move_card_target_column_missing(self) -> None:
        board = self._populated()
        result = board.move_card("k1", "ca", "missing", requested_position=None)
        assert isinstance(result, Err)
        assert result.error == KanbanError.INVALID_CARD_MOVE

    def test_move_card_source_column_missing(self) -> None:
        board = self._populated()
        result = board.move_card("k1", "missing", "cb", requested_position=None)
        assert isinstance(result, Err)
        assert result.error == KanbanError.INVALID_CARD_MOVE

    def test_move_card_card_not_present_in_source(self) -> None:
        board = self._populated()
        result = board.move_card("absent", "ca", "cb", requested_position=None)
        assert isinstance(result, Err)
        assert result.error == KanbanError.CARD_NOT_FOUND

    def test_move_card_within_same_column_card_not_present(self) -> None:
        # Previously this branch silently returned Ok(None) without ever
        # touching the card, masking client bugs. It must now report the
        # missing card explicitly.
        board = self._populated()
        result = board.move_card("absent", "ca", "ca", requested_position=0)
        assert isinstance(result, Err)
        assert result.error == KanbanError.CARD_NOT_FOUND

    def test_move_card_position_beyond_target_returns_invalid_position(self) -> None:
        board = self._populated()
        result = board.move_card("k1", "ca", "cb", requested_position=99)
        assert isinstance(result, Err)
        assert result.error == KanbanError.INVALID_POSITION

    def test_move_card_within_column_position_beyond_bounds(self) -> None:
        # Source==target frees one slot, so for a single-card column the
        # only valid in-place position is 0.
        board = self._populated()
        result = board.move_card("k1", "ca", "ca", requested_position=5)
        assert isinstance(result, Err)
        assert result.error == KanbanError.INVALID_POSITION
