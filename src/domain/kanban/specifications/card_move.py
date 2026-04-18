from __future__ import annotations

from dataclasses import dataclass

from src.domain.kanban.specifications.base import Specification


@dataclass(frozen=True, slots=True)
class CardMoveCandidate:
    target_column_exists: bool
    current_board_id: str | None
    target_board_id: str | None


class TargetColumnExistsSpecification(Specification[CardMoveCandidate]):
    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return candidate.target_column_exists


class SameBoardMoveSpecification(Specification[CardMoveCandidate]):
    def is_satisfied_by(self, candidate: CardMoveCandidate) -> bool:
        return (
            candidate.current_board_id is not None
            and candidate.target_board_id is not None
            and candidate.current_board_id == candidate.target_board_id
        )
