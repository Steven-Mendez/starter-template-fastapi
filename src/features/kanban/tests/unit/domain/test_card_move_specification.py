"""Unit tests for Kanban domain card move specification behavior."""

from __future__ import annotations

import pytest

from src.features.kanban.domain.specifications.card_move import (
    CardMoveCandidate,
    SameBoardMoveSpecification,
    TargetColumnExistsSpecification,
    ValidCardMoveSpecification,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "candidate,expected",
    [
        (CardMoveCandidate(True, "b1", "b1"), True),
        (CardMoveCandidate(False, "b1", "b1"), False),
        (CardMoveCandidate(True, "b1", "b2"), False),
        (CardMoveCandidate(True, None, "b1"), False),
        (CardMoveCandidate(True, "b1", None), False),
    ],
)
def test_valid_card_move_specification(
    candidate: CardMoveCandidate, expected: bool
) -> None:
    assert ValidCardMoveSpecification().is_satisfied_by(candidate) is expected


def test_target_column_exists_branch() -> None:
    spec = TargetColumnExistsSpecification()
    assert spec.is_satisfied_by(CardMoveCandidate(True, "b", "b")) is True
    assert spec.is_satisfied_by(CardMoveCandidate(False, "b", "b")) is False


def test_same_board_branch() -> None:
    spec = SameBoardMoveSpecification()
    assert spec.is_satisfied_by(CardMoveCandidate(True, "b", "b")) is True
    assert spec.is_satisfied_by(CardMoveCandidate(True, "b", "c")) is False
    assert spec.is_satisfied_by(CardMoveCandidate(True, None, "b")) is False
