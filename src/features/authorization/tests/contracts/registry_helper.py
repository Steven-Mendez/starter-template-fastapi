"""Shared registry fixture for authorization tests.

Most tests don't care about the registration mechanics — they just need
a registry seeded with the same resource types the production composition
roots wire up. ``make_test_registry`` returns one such registry so test
churn stays proportional to actual coverage.
"""

from __future__ import annotations

from src.features.authorization.application.registry import (
    AuthorizationRegistry,
)


def make_test_registry() -> AuthorizationRegistry:
    """Return a registry pre-populated with kanban + system resource types.

    Inherited types (column, card) declare a no-op ``parent_of`` because
    most tests do not exercise the parent walk. Tests that need the walk
    install their own callables by registering after construction (the
    registry is unsealed) or by building a fresh one.
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
    return registry
