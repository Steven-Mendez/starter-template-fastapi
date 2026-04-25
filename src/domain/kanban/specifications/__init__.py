"""Domain specifications for the Kanban bounded context."""

from src.domain.kanban.specifications.base import PredicateSpecification, Specification
from src.domain.kanban.specifications.card_move import (
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
