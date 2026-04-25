from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from src.api.schemas.kanban import (
    BoardCreate,
    CardCreate,
    CardPrioritySchema,
    CardUpdate,
)

pytestmark = pytest.mark.unit


def test_board_create_requires_non_empty_title() -> None:
    with pytest.raises(ValidationError):
        BoardCreate.model_validate({"title": ""})


def test_card_create_priority_validation_accepts_enum_and_rejects_garbage() -> None:
    for raw in ("urgent", "P1", ""):
        with pytest.raises(ValidationError):
            CardCreate.model_validate({"title": "x", "priority": raw})
    for p in CardPrioritySchema:
        c = CardCreate.model_validate({"title": "x", "priority": p.value})
        assert c.priority is p
    assert (
        CardCreate.model_validate({"title": "x"}).priority is CardPrioritySchema.MEDIUM
    )


def test_card_create_due_at_optional_iso8601() -> None:
    c = CardCreate.model_validate(
        {
            "title": "x",
            "due_at": "2030-01-15T12:00:00+00:00",
        }
    )
    assert c.due_at == datetime(2030, 1, 15, 12, 0, tzinfo=timezone.utc)
    assert CardCreate.model_validate({"title": "x"}).due_at is None


def test_card_update_column_id_must_be_valid_uuid() -> None:
    with pytest.raises(ValidationError):
        CardUpdate.model_validate({"column_id": "not-a-uuid"})


def test_card_update_valid_uuid_column_id() -> None:
    card_update = CardUpdate.model_validate(
        {"column_id": "00000000-0000-4000-8000-000000000001"}
    )

    assert card_update.column_id == UUID("00000000-0000-4000-8000-000000000001")
