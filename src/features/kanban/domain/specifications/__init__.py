"""Domain specifications for the Kanban bounded context."""

from src.features.kanban.domain.specifications.base import (
    PredicateSpecification,
    Specification,
)
from src.features.kanban.domain.specifications.card_move import (
    CardMoveCandidate,
    SameBoardMoveSpecification,
    TargetColumnExistsSpecification,
    ValidCardMoveSpecification,
)

__all__ = [
    "CardMoveCandidate",
    "PredicateSpecification",
    "SameBoardMoveSpecification",
    "Specification",
    "TargetColumnExistsSpecification",
    "ValidCardMoveSpecification",
]
