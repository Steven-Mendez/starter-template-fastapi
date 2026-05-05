from __future__ import annotations

import pytest

from src.features.kanban.domain.models import Card, CardPriority, Column

pytestmark = pytest.mark.unit


def _card(card_id: str, position: int) -> Card:
    return Card(
        id=card_id,
        column_id="c",
        title=card_id,
        description=None,
        position=position,
        priority=CardPriority.LOW,
        due_at=None,
    )


def test_insert_card_appends_when_no_position() -> None:
    col = Column(id="c", board_id="b", title="t", position=0)
    col.insert_card(_card("a", 0))
    col.insert_card(_card("b", 0))
    assert [c.id for c in col.cards] == ["a", "b"]
    assert [c.position for c in col.cards] == [0, 1]


def test_insert_card_at_position_clamps() -> None:
    col = Column(id="c", board_id="b", title="t", position=0)
    col.insert_card(_card("a", 0))
    col.insert_card(_card("b", 0))
    col.insert_card(_card("z", 0), requested_position=99)
    assert [c.id for c in col.cards] == ["a", "b", "z"]


def test_extract_card_returns_card_and_recalculates_positions() -> None:
    col = Column(id="c", board_id="b", title="t", position=0)
    for cid in ["a", "b", "c"]:
        col.insert_card(_card(cid, 0))
    extracted = col.extract_card("b")
    assert extracted is not None and extracted.id == "b"
    assert [c.id for c in col.cards] == ["a", "c"]
    assert [c.position for c in col.cards] == [0, 1]


def test_extract_missing_card_returns_none() -> None:
    col = Column(id="c", board_id="b", title="t", position=0)
    col.insert_card(_card("a", 0))
    assert col.extract_card("missing") is None


def test_move_card_within_changes_order() -> None:
    col = Column(id="c", board_id="b", title="t", position=0)
    for cid in ["a", "b", "c"]:
        col.insert_card(_card(cid, 0))
    col.move_card_within("a", 2)
    assert [c.id for c in col.cards] == ["b", "c", "a"]


def test_insert_card_overwrites_column_id_to_match_target() -> None:
    col = Column(id="target", board_id="b", title="t", position=0)
    card = _card("a", 0)
    card.column_id = "other"
    col.insert_card(card)
    assert card.column_id == "target"
