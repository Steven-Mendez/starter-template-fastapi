"""Kanban column entity and card ordering behavior."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.features.kanban.domain.models.card import Card


@dataclass(slots=True)
class Column:
    """Entity that owns an ordered list of cards within a board.

    Methods on this class are the only legitimate way to mutate
    ``cards`` so positions stay contiguous and the parent ``board_id``
    stays consistent on each card.
    """

    id: str
    board_id: str
    title: str
    position: int
    cards: list[Card] = field(default_factory=list)

    def extract_card(self, card_id: str) -> Card | None:
        """Remove and return ``card_id`` from this column, re-compacting positions."""
        for i, card in enumerate(self.cards):
            if card.id == card_id:
                extracted = self.cards.pop(i)
                self._recalculate_positions()
                return extracted
        return None

    def insert_card(self, card: Card, requested_position: int | None = None) -> None:
        """Insert ``card`` at ``requested_position`` (clamped to bounds), or append.

        The card's ``column_id`` is rewired to the receiving column so
        callers do not have to remember to update it themselves.
        """
        card.column_id = self.id
        if requested_position is None:
            self.cards.append(card)
        else:
            # Clamp the requested position to the legal range so an
            # invalid value drops the card at the nearest end instead of
            # raising or producing a sparse list.
            bounded_pos = min(max(0, requested_position), len(self.cards))
            self.cards.insert(bounded_pos, card)
        self._recalculate_positions()

    def move_card_within(self, card_id: str, requested_position: int) -> None:
        """Reorder a card inside this column by extracting and reinserting it."""
        card = self.extract_card(card_id)
        if card:
            self.insert_card(card, requested_position)

    def _recalculate_positions(self) -> None:
        """Renumber cards so positions stay contiguous after extract/insert."""
        for i, card in enumerate(self.cards):
            card.position = i
