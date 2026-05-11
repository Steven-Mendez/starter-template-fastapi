"""Glue functions that mount Kanban routes and bind the container to ``app.state``."""

from __future__ import annotations

from fastapi import FastAPI

from src.features.authorization.application.registry import (
    AuthorizationRegistry,
)
from src.features.kanban.adapters.inbound.http.router import (
    build_kanban_api_router,
    build_kanban_health_router,
)
from src.features.kanban.application.ports.outbound import KanbanLookupRepositoryPort
from src.features.kanban.composition.app_state import set_kanban_container
from src.features.kanban.composition.container import KanbanContainer

_KANBAN_ACTIONS: dict[str, frozenset[str]] = {
    "read": frozenset({"reader", "writer", "owner"}),
    "update": frozenset({"writer", "owner"}),
    "delete": frozenset({"owner"}),
}

_KANBAN_HIERARCHY: dict[str, frozenset[str]] = {
    "reader": frozenset({"reader", "writer", "owner"}),
    "writer": frozenset({"writer", "owner"}),
    "owner": frozenset({"owner"}),
}


def register_kanban_authorization(
    registry: AuthorizationRegistry, lookup: KanbanLookupRepositoryPort
) -> None:
    """Register kanban's resource types, hierarchy, and parent walks.

    Called once at composition time. Boards are the leaf resource type
    (their relationship tuples are persisted); columns and cards inherit
    via the lookup repository's parent-id lookups. Multi-level walks
    (``card → column → board``) compose through ``inherits_from``.
    """
    registry.register_resource_type(
        "kanban", actions=_KANBAN_ACTIONS, hierarchy=_KANBAN_HIERARCHY
    )

    def _parent_of_column(column_id: str) -> tuple[str, str] | None:
        board_id = lookup.find_board_id_by_column(column_id)
        if board_id is None:
            return None
        return ("kanban", board_id)

    def _parent_of_card(card_id: str) -> tuple[str, str] | None:
        # The card walks to its column; ``column → kanban`` finishes the
        # chain through the registry's iterative resolver.
        column_id = lookup.find_column_id_by_card(card_id)
        if column_id is None:
            return None
        return ("column", column_id)

    registry.register_parent(
        "column", parent_of=_parent_of_column, inherits_from="kanban"
    )
    registry.register_parent("card", parent_of=_parent_of_card, inherits_from="column")


def mount_kanban_routes(app: FastAPI) -> None:
    """Mount the Kanban HTTP routers.

    The Kanban resource API is exposed under ``/api`` and the readiness probe
    at ``/health`` (root level). Per-route ``require_authorization`` checks
    handle ReBAC; the router enforces only authentication.
    """
    app.include_router(build_kanban_api_router())
    app.include_router(build_kanban_health_router())


def attach_kanban_container(app: FastAPI, container: KanbanContainer) -> None:
    """Bind a Kanban container to ``app.state`` (called during lifespan startup)."""
    set_kanban_container(app, container)


def register_kanban(app: FastAPI, container: KanbanContainer) -> None:
    """Convenience: mount routes and bind container in one call."""
    mount_kanban_routes(app)
    attach_kanban_container(app, container)
