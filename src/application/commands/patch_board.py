from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PatchBoardCommand:
    board_id: str
    title: str
