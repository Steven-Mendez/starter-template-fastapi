"""Shared registry fixture for authorization tests.

Most tests don't care about the registration mechanics — they just need
a registry seeded with a representative resource type. ``make_test_registry``
returns one such registry seeded with two synthetic types — ``system`` and
``thing`` — so test churn stays proportional to actual coverage and the
contract suite stays free of feature-specific vocabulary.
"""

from __future__ import annotations

from src.features.authorization.application.registry import (
    AuthorizationRegistry,
)


def make_test_registry() -> AuthorizationRegistry:
    """Return a registry pre-populated with ``system`` and ``thing`` types.

    The ``thing`` type is a synthetic leaf resource used by the
    AuthorizationPort contract suite: it has the canonical
    ``owner ⊇ writer ⊇ reader`` hierarchy and is intentionally not
    coupled to any feature's vocabulary. Tests that need a parent walk
    install their own callables by registering after construction
    (the registry is unsealed) or by building a fresh one.
    """
    registry = AuthorizationRegistry()
    registry.register_resource_type(
        "system",
        actions={
            "manage_users": frozenset({"admin"}),
            "read_audit": frozenset({"admin"}),
        },
        hierarchy={"admin": frozenset({"admin"})},
    )
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
    return registry
