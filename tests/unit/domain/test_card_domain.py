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


def test_apply_patch_updates_selected_fields() -> None:
    due_at = datetime(2031, 5, 20, tzinfo=UTC)
    next_due_at = datetime(2031, 6, 10, tzinfo=UTC)
    card = Card(
        id="card-3",
        column_id="col-1",
        title="Task",
        description="Old",
        position=0,
        priority=CardPriority.MEDIUM,
        due_at=due_at,
    )

    card.apply_patch(
        title="Task v2",
        description="New",
        priority=CardPriority.HIGH,
        due_at=next_due_at,
    )

    assert card.title == "Task v2"
    assert card.description == "New"
    assert card.priority == CardPriority.HIGH
    assert card.due_at == next_due_at


def test_apply_patch_can_clear_due_at() -> None:
    due_at = datetime(2031, 5, 20, tzinfo=UTC)
    card = Card(
        id="card-4",
        column_id="col-1",
        title="Task",
        description=None,
        position=0,
        priority=CardPriority.MEDIUM,
        due_at=due_at,
    )

    card.apply_patch(clear_due_at=True)

    assert card.due_at is None
