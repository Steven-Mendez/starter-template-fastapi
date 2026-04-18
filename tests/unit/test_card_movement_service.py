from __future__ import annotations

import pytest

from src.domain.kanban.services.card_movement import (
    reorder_between_columns,
    reorder_within_column,
    validate_card_move,
)
from src.domain.kanban.specifications.card_move import CardMoveCandidate
from src.domain.shared.errors import KanbanError

pytestmark = pytest.mark.unit


def test_validate_card_move_requires_existing_target() -> None:
    candidate = CardMoveCandidate(
        target_column_exists=False,
        current_board_id="board-1",
        target_board_id=None,
    )
    assert validate_card_move(candidate) is KanbanError.COLUMN_NOT_FOUND


def test_validate_card_move_requires_same_board() -> None:
    candidate = CardMoveCandidate(
        target_column_exists=True,
        current_board_id="board-1",
        target_board_id="board-2",
    )
    assert validate_card_move(candidate) is KanbanError.INVALID_CARD_MOVE


def test_reorder_within_column_bounds_requested_position() -> None:
    ordered = reorder_within_column(
        moving_card_id="b",
        ordered_card_ids=["a", "b", "c"],
        requested_position=99,
    )
    assert ordered == ["a", "c", "b"]


def test_reorder_between_columns_renumbers_source_and_target() -> None:
    source, target = reorder_between_columns(
        moving_card_id="b",
        source_ordered_card_ids=["a", "b", "c"],
        target_ordered_card_ids=["x", "y"],
        requested_position=1,
    )
    assert source == ["a", "c"]
    assert target == ["x", "b", "y"]
