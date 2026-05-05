from __future__ import annotations

from datetime import datetime, timezone

import pytest

from src.features.kanban.domain.models import Card, CardPriority

pytestmark = pytest.mark.unit


def _card() -> Card:
    return Card(
        id="k1",
        column_id="c",
        title="orig",
        description="desc",
        position=0,
        priority=CardPriority.LOW,
        due_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_apply_patch_no_changes_keeps_state() -> None:
    card = _card()
    snapshot = (card.title, card.description, card.priority, card.due_at)
    card.apply_patch()
    assert (card.title, card.description, card.priority, card.due_at) == snapshot


def test_apply_patch_updates_title() -> None:
    card = _card()
    card.apply_patch(title="new")
    assert card.title == "new"


def test_apply_patch_clear_due_at_sets_none() -> None:
    card = _card()
    card.apply_patch(clear_due_at=True)
    assert card.due_at is None


def test_apply_patch_sets_due_at_to_provided() -> None:
    card = _card()
    new_due = datetime(2026, 6, 1, tzinfo=timezone.utc)
    card.apply_patch(due_at=new_due)
    assert card.due_at == new_due


def test_apply_patch_priority_change() -> None:
    card = _card()
    card.apply_patch(priority=CardPriority.HIGH)
    assert card.priority == CardPriority.HIGH
