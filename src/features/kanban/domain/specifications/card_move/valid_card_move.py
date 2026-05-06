"""Composite specification for legal Kanban card moves."""

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
    """Aggregate rule that a card move is legal in the Kanban domain.

    Composes the smaller specifications in the package into a single
    check used by :meth:`Board.move_card`. New constraints are added by
    extending the composition rather than the individual rules.
    """

    def __init__(self) -> None:
        self._spec = SameBoardMoveSpecification().and_spec(
            TargetColumnExistsSpecification()
        )

    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return self._spec.is_satisfied_by(candidate)
