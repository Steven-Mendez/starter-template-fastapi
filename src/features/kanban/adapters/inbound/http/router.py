"""Composers that bundle every Kanban-facing router into mountable APIRouters.

Under ReBAC, the kanban API is gated *per route* with
``require_authorization`` from the platform layer, not by blanket
``require_permissions("kanban:*")`` lists at the router level.

The router applies a single ``Depends(get_current_principal)`` so every
endpoint requires an authenticated principal (this also stamps the
actor id onto ``request.state``); each route then declares its own
resource-scoped authorization check (or, for ``POST /boards`` and
``GET /boards``, manages access internally).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from src.features.kanban.adapters.inbound.http.boards import (
    boards_read_router,
    boards_write_router,
)
from src.features.kanban.adapters.inbound.http.cards import (
    cards_read_router,
    cards_write_router,
)
from src.features.kanban.adapters.inbound.http.columns import columns_write_router
from src.features.kanban.adapters.inbound.http.health import health_router
from src.platform.api.authorization import get_current_principal


def build_kanban_api_router() -> APIRouter:
    """Compose the Kanban-facing API surface mounted at ``/api``."""
    router = APIRouter(
        prefix="/api",
        # All kanban routes require an authenticated principal. Resource-scoped
        # ReBAC checks are declared per route via ``require_authorization``.
        dependencies=[Depends(get_current_principal)],
    )
    router.include_router(boards_read_router)
    router.include_router(boards_write_router)
    router.include_router(columns_write_router)
    router.include_router(cards_read_router)
    router.include_router(cards_write_router)
    return router


def build_kanban_health_router() -> APIRouter:
    """Top-level Kanban-readiness health route mounted at ``/health``."""
    return health_router
