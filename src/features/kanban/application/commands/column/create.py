from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreateColumnCommand:
    board_id: str
    title: str
