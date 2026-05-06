"""Value object describing the facts needed to validate a card move."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CardMoveCandidate:
    """Snapshot of the facts needed to evaluate a card move against the rules.

    Modeling the inputs as a value object keeps each specification in
    the ``card_move`` package focused on a single rule and avoids
    sprawling argument lists.
    """

    target_column_exists: bool
    current_board_id: str | None
    target_board_id: str | None
