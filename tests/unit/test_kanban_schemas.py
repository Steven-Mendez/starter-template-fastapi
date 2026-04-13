from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from kanban.schemas import BoardCreate, CardCreate, CardPriority

pytestmark = pytest.mark.unit


def test_board_create_requires_non_empty_title() -> None:
    with pytest.raises(ValidationError):
        BoardCreate.model_validate({"title": ""})


def test_card_create_priority_validation_accepts_enum_and_rejects_garbage() -> None:
    for raw in ("urgent", "P1", ""):
        with pytest.raises(ValidationError):
            CardCreate.model_validate({"title": "x", "priority": raw})
    for p in CardPriority:
        c = CardCreate.model_validate({"title": "x", "priority": p.value})
        assert c.priority is p
    assert CardCreate.model_validate({"title": "x"}).priority is CardPriority.MEDIUM


def test_card_create_due_at_optional_iso8601() -> None:
    c = CardCreate.model_validate(
        {
            "title": "x",
            "due_at": "2030-01-15T12:00:00+00:00",
        }
    )
    assert c.due_at == datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)
    assert CardCreate.model_validate({"title": "x"}).due_at is None
