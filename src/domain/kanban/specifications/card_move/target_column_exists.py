from __future__ import annotations

from src.domain.kanban.specifications.base import Specification
from src.domain.kanban.specifications.card_move.candidate import CardMoveCandidate


class TargetColumnExistsSpecification(Specification[CardMoveCandidate]):
    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return candidate.target_column_exists
