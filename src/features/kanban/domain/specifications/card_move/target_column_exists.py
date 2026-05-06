"""Specification that requires the target card column to exist."""

from __future__ import annotations

from src.features.kanban.domain.specifications.base import Specification
from src.features.kanban.domain.specifications.card_move.candidate import (
    CardMoveCandidate,
)


class TargetColumnExistsSpecification(Specification[CardMoveCandidate]):
    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return candidate.target_column_exists
