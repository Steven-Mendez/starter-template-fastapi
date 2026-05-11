"""Unit tests for relation hierarchy expansion (registry-driven)."""

from __future__ import annotations

import pytest

from src.features.authorization.application.errors import UnknownActionError
from src.features.authorization.application.hierarchy import expand_relations
from src.features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)

pytestmark = pytest.mark.unit


def test_kanban_owner_satisfies_every_inferior_relation() -> None:
    registry = make_test_registry()
    assert expand_relations(registry, "kanban", frozenset({"reader"})) == frozenset(
        {"reader", "writer", "owner"}
    )
    assert expand_relations(registry, "kanban", frozenset({"writer"})) == frozenset(
        {"writer", "owner"}
    )
    assert expand_relations(registry, "kanban", frozenset({"owner"})) == frozenset(
        {"owner"}
    )


def test_kanban_multiple_relations_take_union_closure() -> None:
    registry = make_test_registry()
    assert expand_relations(
        registry, "kanban", frozenset({"reader", "owner"})
    ) == frozenset({"reader", "writer", "owner"})


def test_inherited_children_reuse_parent_hierarchy() -> None:
    registry = make_test_registry()
    registry.register_parent(
        "column", parent_of=lambda _id: None, inherits_from="kanban"
    )
    registry.register_parent("card", parent_of=lambda _id: None, inherits_from="column")
    for resource_type in ("column", "card"):
        assert expand_relations(
            registry, resource_type, frozenset({"reader"})
        ) == frozenset({"reader", "writer", "owner"})


def test_system_admin_is_self_only() -> None:
    registry = make_test_registry()
    assert expand_relations(registry, "system", frozenset({"admin"})) == frozenset(
        {"admin"}
    )


def test_unknown_resource_type_raises() -> None:
    registry = make_test_registry()
    with pytest.raises(UnknownActionError):
        expand_relations(registry, "orgs", frozenset({"member"}))


def test_unknown_relation_raises() -> None:
    registry = make_test_registry()
    with pytest.raises(UnknownActionError):
        expand_relations(registry, "kanban", frozenset({"viewer"}))
