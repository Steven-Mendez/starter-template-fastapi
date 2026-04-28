from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.domain.kanban.exceptions import InvalidCardMoveError
from src.domain.kanban.models import Board, Card, CardPriority, Column
from src.domain.kanban.specifications.base import PredicateSpecification
from src.domain.kanban.specifications.card_move import (
    CardMoveCandidate,
    SameBoardMoveSpecification,
    TargetColumnExistsSpecification,
    ValidCardMoveSpecification,
)

pytestmark = pytest.mark.unit


def test_specification_and_composition() -> None:
    positive = PredicateSpecification[int](lambda x: x > 0)
    even = PredicateSpecification[int](lambda x: x % 2 == 0)
    composed = positive.and_spec(even)
    assert composed.is_satisfied_by(4) is True
    assert composed.is_satisfied_by(3) is False
    assert composed.is_satisfied_by(-2) is False


def test_specification_or_composition() -> None:
    small = PredicateSpecification[int](lambda x: x < 2)
    large = PredicateSpecification[int](lambda x: x > 10)
    composed = small.or_spec(large)
    assert composed.is_satisfied_by(1) is True
    assert composed.is_satisfied_by(11) is True
    assert composed.is_satisfied_by(5) is False


def test_specification_not_composition() -> None:
    positive = PredicateSpecification[int](lambda x: x > 0)
    negative_or_zero = positive.not_spec()
    assert negative_or_zero.is_satisfied_by(-1) is True
    assert negative_or_zero.is_satisfied_by(0) is True
    assert negative_or_zero.is_satisfied_by(1) is False


def test_card_move_specifications_validate_candidate() -> None:
    candidate = CardMoveCandidate(
        target_column_exists=True,
        current_board_id="board-1",
        target_board_id="board-1",
    )
    composed = TargetColumnExistsSpecification().and_spec(SameBoardMoveSpecification())
    assert composed.is_satisfied_by(candidate) is True


def test_card_move_specification_detects_cross_board() -> None:
    candidate = CardMoveCandidate(
        target_column_exists=True,
        current_board_id="board-1",
        target_board_id="board-2",
    )
    composed = TargetColumnExistsSpecification().and_spec(SameBoardMoveSpecification())
    assert composed.is_satisfied_by(candidate) is False


def test_valid_card_move_spec_satisfied_for_same_board() -> None:
    candidate = CardMoveCandidate(
        target_column_exists=True,
        current_board_id="board-1",
        target_board_id="board-1",
    )

    assert ValidCardMoveSpecification().is_satisfied_by(candidate) is True


def test_valid_card_move_spec_fails_for_cross_board() -> None:
    candidate = CardMoveCandidate(
        target_column_exists=True,
        current_board_id="board-1",
        target_board_id="board-2",
    )

    assert ValidCardMoveSpecification().is_satisfied_by(candidate) is False


def test_valid_card_move_spec_fails_when_target_column_missing() -> None:
    candidate = CardMoveCandidate(
        target_column_exists=False,
        current_board_id="board-1",
        target_board_id="board-1",
    )

    assert ValidCardMoveSpecification().is_satisfied_by(candidate) is False


def test_board_move_card_rejects_move_when_target_column_missing() -> None:
    source_column = Column(
        id="col-1",
        board_id="board-1",
        title="Todo",
        position=0,
        cards=[
            Card(
                id="card-1",
                column_id="col-1",
                title="Task",
                description=None,
                position=0,
                priority=CardPriority.MEDIUM,
                due_at=None,
            )
        ],
    )
    board = Board(
        id="board-1",
        title="Board",
        created_at=datetime.now(tz=timezone.utc),
        columns=[source_column],
    )

    with pytest.raises(InvalidCardMoveError):
        board.move_card(
            card_id="card-1",
            source_column_id="col-1",
            target_column_id="missing-column",
            requested_position=None,
        )


def test_board_move_card_moves_between_columns_when_spec_satisfied() -> None:
    source_column = Column(
        id="col-1",
        board_id="board-1",
        title="Todo",
        position=0,
        cards=[
            Card(
                id="card-1",
                column_id="col-1",
                title="Task",
                description=None,
                position=0,
                priority=CardPriority.MEDIUM,
                due_at=None,
            )
        ],
    )
    target_column = Column(
        id="col-2",
        board_id="board-1",
        title="Doing",
        position=1,
        cards=[],
    )
    board = Board(
        id="board-1",
        title="Board",
        created_at=datetime.now(tz=timezone.utc),
        columns=[source_column, target_column],
    )

    board.move_card(
        card_id="card-1",
        source_column_id="col-1",
        target_column_id="col-2",
        requested_position=None,
    )

    assert source_column.cards == []
    assert len(target_column.cards) == 1
    assert target_column.cards[0].id == "card-1"
    assert target_column.cards[0].column_id == "col-2"
