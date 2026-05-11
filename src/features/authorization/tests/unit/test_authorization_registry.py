"""Unit tests for the ``AuthorizationRegistry`` runtime contract."""

from __future__ import annotations

import pytest

from src.features.authorization.application.errors import UnknownActionError
from src.features.authorization.application.registry import (
    AuthorizationRegistry,
)

pytestmark = pytest.mark.unit


def _seed_kanban(registry: AuthorizationRegistry) -> None:
    registry.register_resource_type(
        "kanban",
        actions={
            "read": frozenset({"reader", "writer", "owner"}),
            "update": frozenset({"writer", "owner"}),
            "delete": frozenset({"owner"}),
        },
        hierarchy={
            "reader": frozenset({"reader", "writer", "owner"}),
            "writer": frozenset({"writer", "owner"}),
            "owner": frozenset({"owner"}),
        },
    )


def test_register_resource_type_then_lookup_returns_actions_and_hierarchy() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    assert registry.relations_for("kanban", "read") == frozenset(
        {"reader", "writer", "owner"}
    )
    assert registry.expand_relations("kanban", frozenset({"writer"})) == frozenset(
        {"writer", "owner"}
    )
    assert registry.has_stored_relations("kanban") is True


def test_register_parent_inherits_actions_and_hierarchy_from_parent() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    registry.register_parent(
        "column",
        parent_of=lambda column_id: ("kanban", f"board-for-{column_id}"),
        inherits_from="kanban",
    )
    assert registry.relations_for("column", "update") == frozenset({"writer", "owner"})
    assert registry.parent_of("column", "c1") == ("kanban", "board-for-c1")
    assert registry.has_stored_relations("column") is False


def test_register_parent_supports_multi_level_inheritance_chain() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    registry.register_parent(
        "column",
        parent_of=lambda column_id: ("kanban", "b1"),
        inherits_from="kanban",
    )
    registry.register_parent(
        "card",
        parent_of=lambda card_id: ("column", "col1"),
        inherits_from="column",
    )
    assert registry.relations_for("card", "delete") == frozenset({"owner"})
    assert registry.expand_relations("card", frozenset({"reader"})) == frozenset(
        {"reader", "writer", "owner"}
    )


def test_duplicate_register_resource_type_raises_value_error() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    with pytest.raises(ValueError, match="kanban"):
        registry.register_resource_type("kanban", actions={}, hierarchy={})


def test_duplicate_register_parent_raises_value_error() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    registry.register_parent(
        "column",
        parent_of=lambda _id: None,
        inherits_from="kanban",
    )
    with pytest.raises(ValueError, match="column"):
        registry.register_parent(
            "column",
            parent_of=lambda _id: None,
            inherits_from="kanban",
        )


def test_register_after_seal_raises_runtime_error() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    registry.seal()
    with pytest.raises(RuntimeError):
        registry.register_resource_type("system", actions={}, hierarchy={})
    with pytest.raises(RuntimeError):
        registry.register_parent(
            "column", parent_of=lambda _id: None, inherits_from="kanban"
        )


def test_read_methods_still_work_after_seal() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    registry.seal()
    assert registry.relations_for("kanban", "read") == frozenset(
        {"reader", "writer", "owner"}
    )


def test_relations_for_unknown_resource_type_raises_unknown_action() -> None:
    registry = AuthorizationRegistry()
    with pytest.raises(UnknownActionError):
        registry.relations_for("orgs", "read")


def test_relations_for_unknown_action_raises_unknown_action() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    with pytest.raises(UnknownActionError):
        registry.relations_for("kanban", "purge")


def test_expand_relations_unknown_relation_raises_unknown_action() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    with pytest.raises(UnknownActionError):
        registry.expand_relations("kanban", frozenset({"viewer"}))


def test_parent_of_returns_none_for_leaf_types() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    assert registry.parent_of("kanban", "any-id") is None


def test_parent_of_propagates_none_from_callable() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    registry.register_parent(
        "column",
        parent_of=lambda _id: None,
        inherits_from="kanban",
    )
    assert registry.parent_of("column", "missing") is None


def test_nearest_leaf_type_is_identity_for_leaves() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    assert registry.nearest_leaf_type("kanban") == "kanban"


def test_nearest_leaf_type_walks_inherits_from_chain() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    registry.register_parent(
        "column",
        parent_of=lambda _id: ("kanban", "b1"),
        inherits_from="kanban",
    )
    registry.register_parent(
        "card",
        parent_of=lambda _id: ("column", "c1"),
        inherits_from="column",
    )
    assert registry.nearest_leaf_type("column") == "kanban"
    assert registry.nearest_leaf_type("card") == "kanban"


def test_nearest_leaf_type_unknown_raises() -> None:
    registry = AuthorizationRegistry()
    with pytest.raises(UnknownActionError):
        registry.nearest_leaf_type("orgs")


def test_registered_resource_types_includes_leaves_and_inherited() -> None:
    registry = AuthorizationRegistry()
    _seed_kanban(registry)
    registry.register_parent(
        "column",
        parent_of=lambda _id: None,
        inherits_from="kanban",
    )
    assert registry.registered_resource_types() == {"kanban", "column"}
