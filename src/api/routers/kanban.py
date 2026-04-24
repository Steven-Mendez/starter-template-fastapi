from __future__ import annotations

from fastapi import APIRouter

from src.api.routers.boards import boards_router
from src.api.routers.cards import cards_router
from src.api.routers.columns import columns_router

kanban_router = APIRouter(prefix="/api", tags=["kanban"])
kanban_router.include_router(boards_router)
kanban_router.include_router(columns_router)
kanban_router.include_router(cards_router)
