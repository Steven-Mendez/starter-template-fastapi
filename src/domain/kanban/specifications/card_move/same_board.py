from __future__ import annotations

from src.domain.kanban.specifications.base import Specification
from src.domain.kanban.specifications.card_move.candidate import CardMoveCandidate


class SameBoardMoveSpecification(Specification[CardMoveCandidate]):
    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return (
            candidate.current_board_id is not None
            and candidate.target_board_id is not None
            and candidate.current_board_id == candidate.target_board_id
        )
