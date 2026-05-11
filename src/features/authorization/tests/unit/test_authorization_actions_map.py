"""Unit tests for the action -> required-relations dispatch contract.

Actions are now registered on an :class:`AuthorizationRegistry` at
composition time; these tests assert against the seeded registry the
test helper produces.
"""

from __future__ import annotations

import pytest

from src.features.authorization.application.actions import relations_for
from src.features.authorization.application.errors import UnknownActionError
from src.features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)

pytestmark = pytest.mark.unit


def test_kanban_action_mappings_match_spec() -> None:
    registry = make_test_registry()
    assert relations_for(registry, "kanban", "read") == frozenset(
        {"reader", "writer", "owner"}
    )
    assert relations_for(registry, "kanban", "update") == frozenset({"writer", "owner"})
    assert relations_for(registry, "kanban", "delete") == frozenset({"owner"})


def test_system_action_mappings_match_spec() -> None:
    registry = make_test_registry()
    assert relations_for(registry, "system", "manage_users") == frozenset({"admin"})
    assert relations_for(registry, "system", "read_audit") == frozenset({"admin"})


def test_inherited_children_share_kanban_actions() -> None:
    """Inherited resource types reuse their parent's registered action map."""
    registry = make_test_registry()
    registry.register_parent(
        "column", parent_of=lambda _id: None, inherits_from="kanban"
    )
    registry.register_parent("card", parent_of=lambda _id: None, inherits_from="column")
    assert relations_for(registry, "column", "delete") == frozenset({"owner"})
    assert relations_for(registry, "card", "read") == frozenset(
        {"reader", "writer", "owner"}
    )


def test_relations_for_unknown_resource_type_raises() -> None:
    registry = make_test_registry()
    with pytest.raises(UnknownActionError):
        relations_for(registry, "orgs", "read")


def test_relations_for_unknown_action_raises() -> None:
    registry = make_test_registry()
    with pytest.raises(UnknownActionError):
        relations_for(registry, "kanban", "purge")


def test_relations_for_returns_the_mapped_set() -> None:
    registry = make_test_registry()
    assert relations_for(registry, "kanban", "delete") == frozenset({"owner"})
    assert relations_for(registry, "system", "manage_users") == frozenset({"admin"})
