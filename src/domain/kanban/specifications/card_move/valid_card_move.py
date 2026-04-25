from __future__ import annotations

from src.domain.kanban.specifications.base import Specification
from src.domain.kanban.specifications.card_move.candidate import CardMoveCandidate
from src.domain.kanban.specifications.card_move.same_board import (
    SameBoardMoveSpecification,
)
from src.domain.kanban.specifications.card_move.target_column_exists import (
    TargetColumnExistsSpecification,
)


class ValidCardMoveSpecification(Specification[CardMoveCandidate]):
    def __init__(self) -> None:
        self._spec = SameBoardMoveSpecification().and_spec(
            TargetColumnExistsSpecification()
        )

    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return self._spec.is_satisfied_by(candidate)
