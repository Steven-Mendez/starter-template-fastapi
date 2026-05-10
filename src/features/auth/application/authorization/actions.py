"""Action -> required-relations dispatch table.

Adding a new HTTP action requires only an entry here; no schema change.
The map is the single source of truth shared by routes, the engine, and
tests. Adapters consume it via the port; SpiceDB-shaped adapters could
translate it into a ``.zed`` schema at startup.
"""

from __future__ import annotations

from src.features.auth.application.authorization.errors import UnknownActionError

# ── Kanban ────────────────────────────────────────────────────────────────────
#
# Kanban resources (board, column, card) share the same relation hierarchy.
# Column and card actions resolve via parent walk to the owning board, so
# the same mappings apply to any kanban-flavoured resource type.

KANBAN_ACTIONS: dict[str, frozenset[str]] = {
    "read": frozenset({"reader", "writer", "owner"}),
    "update": frozenset({"writer", "owner"}),
    "delete": frozenset({"owner"}),
}

# ── System ────────────────────────────────────────────────────────────────────

SYSTEM_ACTIONS: dict[str, frozenset[str]] = {
    "manage_users": frozenset({"admin"}),
    "read_audit": frozenset({"admin"}),
}


ACTIONS: dict[str, dict[str, frozenset[str]]] = {
    "kanban": KANBAN_ACTIONS,
    # ``column`` and ``card`` reuse the kanban action map; the engine walks
    # to the parent board to evaluate the check. Aliasing here makes the
    # cross-resource inheritance explicit at the contract layer.
    "column": KANBAN_ACTIONS,
    "card": KANBAN_ACTIONS,
    "system": SYSTEM_ACTIONS,
}


def relations_for(resource_type: str, action: str) -> frozenset[str]:
    """Return the relation set that satisfies ``action`` on ``resource_type``.

    Raises:
        UnknownActionError: If the pair is not present in ``ACTIONS``.
            Treat as a programmer error: every route-mounted action must
            declare its relations here.
    """
    by_action = ACTIONS.get(resource_type)
    if by_action is None:
        raise UnknownActionError(
            f"Unknown resource_type for authorization: {resource_type!r}"
        )
    relations = by_action.get(action)
    if relations is None:
        raise UnknownActionError(
            f"Unknown action {action!r} for resource_type {resource_type!r}"
        )
    return relations
