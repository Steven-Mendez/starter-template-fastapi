from __future__ import annotations

import pytest

from src.domain.kanban.models import Card, CardPriority, Column

pytestmark = pytest.mark.unit


def _make_card(card_id: str, title: str, position: int = 0) -> Card:
    return Card(
        id=card_id,
        column_id="col-1",
        title=title,
        description=None,
        position=position,
        priority=CardPriority.MEDIUM,
        due_at=None,
    )


def _make_column(column_id: str = "col-1") -> Column:
    return Column(id=column_id, board_id="board-1", title="To Do", position=0)


def test_insert_card_appends_when_no_position() -> None:
    column = _make_column()
    card = _make_card("c1", "First")

    column.insert_card(card)

    assert [c.id for c in column.cards] == ["c1"]
    assert [c.position for c in column.cards] == [0]


def test_insert_card_at_position_zero_places_at_head() -> None:
    column = _make_column()
    column.insert_card(_make_card("c1", "First"))
    new_card = _make_card("c2", "Head")

    column.insert_card(new_card, requested_position=0)

    assert [c.id for c in column.cards] == ["c2", "c1"]
    assert [c.position for c in column.cards] == [0, 1]


def test_insert_card_beyond_end_clamps_to_tail() -> None:
    column = _make_column()
    column.insert_card(_make_card("c1", "First"))

    column.insert_card(_make_card("c2", "Tail"), requested_position=999)

    assert [c.id for c in column.cards] == ["c1", "c2"]
    assert [c.position for c in column.cards] == [0, 1]


def test_extract_card_returns_card_and_removes_from_list() -> None:
    column = _make_column()
    card = _make_card("c1", "Only")
    column.insert_card(card)

    extracted = column.extract_card("c1")

    assert extracted is card
    assert column.cards == []


def test_extract_card_reindexes_remaining_cards() -> None:
    column = _make_column()
    column.insert_card(_make_card("a", "A"))
    column.insert_card(_make_card("b", "B"))
    column.insert_card(_make_card("c", "C"))

    column.extract_card("b")

    assert [card.id for card in column.cards] == ["a", "c"]
    assert [card.position for card in column.cards] == [0, 1]


def test_extract_missing_card_returns_none() -> None:
    column = _make_column()
    column.insert_card(_make_card("a", "A"))

    extracted = column.extract_card("missing")

    assert extracted is None
    assert [card.id for card in column.cards] == ["a"]


def test_move_card_within_reorders_correctly() -> None:
    column = _make_column()
    column.insert_card(_make_card("a", "A"))
    column.insert_card(_make_card("b", "B"))

    column.move_card_within("a", requested_position=1)

    assert [card.id for card in column.cards] == ["b", "a"]
    assert [card.position for card in column.cards] == [0, 1]


def test_column_id_assigned_on_insert() -> None:
    column = _make_column(column_id="col-99")
    card = _make_card("c1", "Moved")
    card.column_id = "another-col"

    column.insert_card(card)

    assert card.column_id == "col-99"
