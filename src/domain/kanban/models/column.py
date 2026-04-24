from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.kanban.models.card import Card


@dataclass(slots=True)
class Column:
    id: str
    board_id: str
    title: str
    position: int
    cards: list[Card] = field(default_factory=list)

    def extract_card(self, card_id: str) -> Card | None:
        for i, card in enumerate(self.cards):
            if card.id == card_id:
                extracted = self.cards.pop(i)
                self._recalculate_positions()
                return extracted
        return None

    def insert_card(self, card: Card, requested_position: int | None = None) -> None:
        card.column_id = self.id
        if requested_position is None:
            self.cards.append(card)
        else:
            bounded_pos = min(max(0, requested_position), len(self.cards))
            self.cards.insert(bounded_pos, card)
        self._recalculate_positions()

    def move_card_within(self, card_id: str, requested_position: int) -> None:
        card = self.extract_card(card_id)
        if card:
            self.insert_card(card, requested_position)

    def _recalculate_positions(self) -> None:
        for i, card in enumerate(self.cards):
            card.position = i
