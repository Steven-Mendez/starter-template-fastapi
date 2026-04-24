from __future__ import annotations

from fastapi import APIRouter

from src.api.routers.health import health_router
from src.api.routers.kanban import kanban_router
from src.api.routers.root import root_router

api_router = APIRouter()
api_router.include_router(root_router)
api_router.include_router(health_router)
api_router.include_router(kanban_router)

__all__ = ["api_router", "health_router", "kanban_router", "root_router"]
