"""Unit tests for relation hierarchy expansion."""

from __future__ import annotations

import pytest

from src.features.auth.application.authorization.errors import UnknownActionError
from src.features.auth.application.authorization.hierarchy import expand_relations

pytestmark = pytest.mark.unit


def test_kanban_owner_satisfies_every_inferior_relation() -> None:
    assert expand_relations("kanban", frozenset({"reader"})) == frozenset(
        {"reader", "writer", "owner"}
    )
    assert expand_relations("kanban", frozenset({"writer"})) == frozenset(
        {"writer", "owner"}
    )
    assert expand_relations("kanban", frozenset({"owner"})) == frozenset({"owner"})


def test_kanban_multiple_relations_take_union_closure() -> None:
    # Reader ∪ owner expands to all three because reader includes the writer
    # set and owner is a no-op increment.
    assert expand_relations("kanban", frozenset({"reader", "owner"})) == frozenset(
        {"reader", "writer", "owner"}
    )


def test_column_and_card_share_kanban_hierarchy() -> None:
    # The engine resolves card/column checks via the parent board, but the
    # hierarchy entries exist so the expansion can run before the walk.
    for resource_type in ("column", "card"):
        assert expand_relations(resource_type, frozenset({"reader"})) == frozenset(
            {"reader", "writer", "owner"}
        )


def test_system_admin_is_self_only() -> None:
    assert expand_relations("system", frozenset({"admin"})) == frozenset({"admin"})


def test_unknown_resource_type_raises() -> None:
    with pytest.raises(UnknownActionError):
        expand_relations("orgs", frozenset({"member"}))


def test_unknown_relation_raises() -> None:
    with pytest.raises(UnknownActionError):
        expand_relations("kanban", frozenset({"viewer"}))
