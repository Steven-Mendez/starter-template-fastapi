from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GetCardQuery:
    card_id: str
