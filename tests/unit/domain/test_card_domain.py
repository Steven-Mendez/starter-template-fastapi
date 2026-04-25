from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.domain.kanban.models import Card, CardPriority

pytestmark = pytest.mark.unit


def test_card_stores_declared_attributes() -> None:
    due_at = datetime(2031, 5, 20, tzinfo=UTC)

    card = Card(
        id="card-1",
        column_id="col-1",
        title="Write tests",
        description="domain-level check",
        position=2,
        priority=CardPriority.MEDIUM,
        due_at=due_at,
    )

    assert card.id == "card-1"
    assert card.column_id == "col-1"
    assert card.title == "Write tests"
    assert card.description == "domain-level check"
    assert card.position == 2
    assert card.priority == CardPriority.MEDIUM
    assert card.due_at == due_at


def test_card_fields_are_mutable_for_domain_reordering() -> None:
    card = Card(
        id="card-2",
        column_id="col-1",
        title="Task",
        description=None,
        position=0,
        priority=CardPriority.LOW,
        due_at=None,
    )

    card.position = 3
    card.column_id = "col-2"

    assert card.position == 3
    assert card.column_id == "col-2"
