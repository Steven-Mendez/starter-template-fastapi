from __future__ import annotations

from src.domain.kanban.specifications.card_move import (
    CardMoveCandidate,
    SameBoardMoveSpecification,
    TargetColumnExistsSpecification,
)
from src.domain.shared.errors import KanbanError


def validate_card_move(candidate: CardMoveCandidate) -> KanbanError | None:
    if not TargetColumnExistsSpecification().is_satisfied_by(candidate):
        return KanbanError.COLUMN_NOT_FOUND
    if not SameBoardMoveSpecification().is_satisfied_by(candidate):
        return KanbanError.INVALID_CARD_MOVE
    return None


def reorder_within_column(
    *, moving_card_id: str, ordered_card_ids: list[str], requested_position: int
) -> list[str]:
    other_ids = [card_id for card_id in ordered_card_ids if card_id != moving_card_id]
    bounded_position = min(max(0, requested_position), len(other_ids))
    return (
        other_ids[:bounded_position]
        + [moving_card_id]
        + other_ids[bounded_position:]
    )


def reorder_between_columns(
    *,
    moving_card_id: str,
    source_ordered_card_ids: list[str],
    target_ordered_card_ids: list[str],
    requested_position: int | None,
) -> tuple[list[str], list[str]]:
    source_ids = [
        card_id for card_id in source_ordered_card_ids if card_id != moving_card_id
    ]
    target_ids = [
        card_id for card_id in target_ordered_card_ids if card_id != moving_card_id
    ]
    position = len(target_ids) if requested_position is None else requested_position
    bounded_position = min(max(0, position), len(target_ids))
    target_ids = (
        target_ids[:bounded_position] + [moving_card_id] + target_ids[bounded_position:]
    )
    return source_ids, target_ids
