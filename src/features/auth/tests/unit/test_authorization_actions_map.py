"""Unit tests for the action -> required-relations dispatch contract."""

from __future__ import annotations

import pytest

from src.features.auth.application.authorization.actions import (
    ACTIONS,
    relations_for,
)
from src.features.auth.application.authorization.errors import UnknownActionError

pytestmark = pytest.mark.unit


def test_kanban_action_mappings_match_spec() -> None:
    assert ACTIONS["kanban"]["read"] == frozenset({"reader", "writer", "owner"})
    assert ACTIONS["kanban"]["update"] == frozenset({"writer", "owner"})
    assert ACTIONS["kanban"]["delete"] == frozenset({"owner"})


def test_system_action_mappings_match_spec() -> None:
    assert ACTIONS["system"]["manage_users"] == frozenset({"admin"})
    assert ACTIONS["system"]["read_audit"] == frozenset({"admin"})


def test_column_and_card_alias_kanban_actions() -> None:
    """Card and column inherit the kanban map; the engine walks the parent chain."""
    assert ACTIONS["column"] is ACTIONS["kanban"]
    assert ACTIONS["card"] is ACTIONS["kanban"]


def test_every_action_set_is_non_empty_frozenset() -> None:
    for resource_type, by_action in ACTIONS.items():
        for action, relations in by_action.items():
            assert isinstance(relations, frozenset), (
                f"{resource_type}.{action} must be a frozenset"
            )
            assert relations, (
                f"{resource_type}.{action} must declare at least one relation"
            )


def test_relations_for_unknown_resource_type_raises() -> None:
    with pytest.raises(UnknownActionError):
        relations_for("orgs", "read")


def test_relations_for_unknown_action_raises() -> None:
    with pytest.raises(UnknownActionError):
        relations_for("kanban", "purge")


def test_relations_for_returns_the_mapped_set() -> None:
    assert relations_for("kanban", "delete") == frozenset({"owner"})
    assert relations_for("system", "manage_users") == frozenset({"admin"})
