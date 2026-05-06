"""Composers that bundle every Kanban-facing router into mountable APIRouters."""

from __future__ import annotations

from fastapi import APIRouter

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


def build_kanban_api_router() -> APIRouter:
    """Compose the Kanban-facing API surface mounted at ``/api``."""
    router = APIRouter(prefix="/api")
    router.include_router(boards_read_router)
    router.include_router(boards_write_router)
    router.include_router(columns_write_router)
    router.include_router(cards_read_router)
    router.include_router(cards_write_router)
    return router


def build_kanban_health_router() -> APIRouter:
    """Top-level Kanban-readiness health route mounted at ``/health``."""
    return health_router
