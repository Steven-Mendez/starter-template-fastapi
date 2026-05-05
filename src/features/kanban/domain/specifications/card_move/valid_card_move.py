from __future__ import annotations

from src.features.kanban.domain.specifications.base import Specification
from src.features.kanban.domain.specifications.card_move.candidate import (
    CardMoveCandidate,
)
from src.features.kanban.domain.specifications.card_move.same_board import (
    SameBoardMoveSpecification,
)
from src.features.kanban.domain.specifications.card_move.target_column_exists import (
    TargetColumnExistsSpecification,
)


class ValidCardMoveSpecification(Specification[CardMoveCandidate]):
    def __init__(self) -> None:
        self._spec = SameBoardMoveSpecification().and_spec(
            TargetColumnExistsSpecification()
        )

    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return self._spec.is_satisfied_by(candidate)
