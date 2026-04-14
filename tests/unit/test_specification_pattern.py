from __future__ import annotations

import pytest

from kanban.card_move_specifications import (
    CardMoveCandidate,
    SameBoardMoveSpecification,
    TargetColumnExistsSpecification,
)
from kanban.specification import PredicateSpecification

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
