from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CardMoveCandidate:
    target_column_exists: bool
    current_board_id: str | None
    target_board_id: str | None
