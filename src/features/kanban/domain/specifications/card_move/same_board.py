"""Specification that keeps card moves within one board."""

from __future__ import annotations

from src.features.kanban.domain.specifications.base import Specification
from src.features.kanban.domain.specifications.card_move.candidate import (
    CardMoveCandidate,
)


class SameBoardMoveSpecification(Specification[CardMoveCandidate]):
    """Holds when both the current and the target column belong to the same board.

    Cross-board moves are intentionally rejected because each board is
    its own consistency boundary and shuffling cards across them would
    require coordinated updates to two aggregates.
    """

    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return (
            candidate.current_board_id is not None
            and candidate.target_board_id is not None
            and candidate.current_board_id == candidate.target_board_id
        )
