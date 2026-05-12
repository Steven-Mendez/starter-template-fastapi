"""Unit tests for the :class:`Thing` aggregate."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.features._template.domain.errors import ThingNameRequiredError
from src.features._template.domain.models.thing import Thing

pytestmark = pytest.mark.unit


def test_create_sets_id_and_timestamps() -> None:
    owner = uuid4()
    thing = Thing.create(name="My thing", owner_id=owner)
    assert thing.name == "My thing"
    assert thing.owner_id == owner
    assert thing.id is not None
    # ``created_at`` and ``updated_at`` are both set by the constructor; their
    # values come from separate calls to ``now()`` so the equality is "close
    # enough", not exact.
    assert abs((thing.updated_at - thing.created_at).total_seconds()) < 1


def test_create_rejects_empty_name() -> None:
    with pytest.raises(ThingNameRequiredError):
        Thing.create(name="", owner_id=uuid4())


def test_create_rejects_whitespace_only_name() -> None:
    with pytest.raises(ThingNameRequiredError):
        Thing.create(name="   ", owner_id=uuid4())


def test_rename_returns_new_instance_with_updated_at_bumped() -> None:
    thing = Thing.create(name="Old", owner_id=uuid4())
    renamed = thing.rename("New")
    assert renamed.name == "New"
    assert renamed.id == thing.id
    assert renamed.updated_at >= thing.updated_at
    # The original is not mutated.
    assert thing.name == "Old"


def test_rename_rejects_empty_name() -> None:
    thing = Thing.create(name="Old", owner_id=uuid4())
    with pytest.raises(ThingNameRequiredError):
        thing.rename("")
