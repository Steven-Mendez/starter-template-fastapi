"""Unit tests for the ``AuthorizationRegistry`` runtime contract."""

from __future__ import annotations

import pytest

from features.authorization.application.errors import UnknownActionError
from features.authorization.application.registry import (
    AuthorizationRegistry,
)

pytestmark = pytest.mark.unit


def _seed_thing(registry: AuthorizationRegistry) -> None:
    registry.register_resource_type(
        "thing",
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
    _seed_thing(registry)
    assert registry.relations_for("thing", "read") == frozenset(
        {"reader", "writer", "owner"}
    )
    assert registry.expand_relations("thing", frozenset({"writer"})) == frozenset(
        {"writer", "owner"}
    )
    assert registry.has_stored_relations("thing") is True


def test_register_parent_inherits_actions_and_hierarchy_from_parent() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    registry.register_parent(
        "column",
        parent_of=lambda column_id: ("thing", f"board-for-{column_id}"),
        inherits_from="thing",
    )
    assert registry.relations_for("column", "update") == frozenset({"writer", "owner"})
    assert registry.parent_of("column", "c1") == ("thing", "board-for-c1")
    assert registry.has_stored_relations("column") is False


def test_register_parent_supports_multi_level_inheritance_chain() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    registry.register_parent(
        "column",
        parent_of=lambda column_id: ("thing", "b1"),
        inherits_from="thing",
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
    _seed_thing(registry)
    with pytest.raises(ValueError, match="thing"):
        registry.register_resource_type("thing", actions={}, hierarchy={})


def test_duplicate_register_parent_raises_value_error() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    registry.register_parent(
        "column",
        parent_of=lambda _id: None,
        inherits_from="thing",
    )
    with pytest.raises(ValueError, match="column"):
        registry.register_parent(
            "column",
            parent_of=lambda _id: None,
            inherits_from="thing",
        )


def test_register_after_seal_raises_runtime_error() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    registry.seal()
    with pytest.raises(RuntimeError):
        registry.register_resource_type("system", actions={}, hierarchy={})
    with pytest.raises(RuntimeError):
        registry.register_parent(
            "column", parent_of=lambda _id: None, inherits_from="thing"
        )


def test_read_methods_still_work_after_seal() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    registry.seal()
    assert registry.relations_for("thing", "read") == frozenset(
        {"reader", "writer", "owner"}
    )


def test_relations_for_unknown_resource_type_raises_unknown_action() -> None:
    registry = AuthorizationRegistry()
    with pytest.raises(UnknownActionError):
        registry.relations_for("orgs", "read")


def test_relations_for_unknown_action_raises_unknown_action() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    with pytest.raises(UnknownActionError):
        registry.relations_for("thing", "purge")


def test_expand_relations_unknown_relation_raises_unknown_action() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    with pytest.raises(UnknownActionError):
        registry.expand_relations("thing", frozenset({"viewer"}))


def test_parent_of_returns_none_for_leaf_types() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    assert registry.parent_of("thing", "any-id") is None


def test_parent_of_propagates_none_from_callable() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    registry.register_parent(
        "column",
        parent_of=lambda _id: None,
        inherits_from="thing",
    )
    assert registry.parent_of("column", "missing") is None


def test_nearest_leaf_type_is_identity_for_leaves() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    assert registry.nearest_leaf_type("thing") == "thing"


def test_nearest_leaf_type_walks_inherits_from_chain() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    registry.register_parent(
        "column",
        parent_of=lambda _id: ("thing", "b1"),
        inherits_from="thing",
    )
    registry.register_parent(
        "card",
        parent_of=lambda _id: ("column", "c1"),
        inherits_from="column",
    )
    assert registry.nearest_leaf_type("column") == "thing"
    assert registry.nearest_leaf_type("card") == "thing"


def test_nearest_leaf_type_unknown_raises() -> None:
    registry = AuthorizationRegistry()
    with pytest.raises(UnknownActionError):
        registry.nearest_leaf_type("orgs")


def test_registered_resource_types_includes_leaves_and_inherited() -> None:
    registry = AuthorizationRegistry()
    _seed_thing(registry)
    registry.register_parent(
        "column",
        parent_of=lambda _id: None,
        inherits_from="thing",
    )
    assert registry.registered_resource_types() == {"thing", "column"}
