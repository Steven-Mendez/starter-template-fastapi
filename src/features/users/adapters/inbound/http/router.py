"""Compose users routers into one mountable APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from src.features.users.adapters.inbound.http.admin import admin_router
from src.features.users.adapters.inbound.http.me import me_router


def build_users_router() -> APIRouter:
    """Return a router exposing the users feature's HTTP endpoints."""
    router = APIRouter()
    router.include_router(me_router)
    router.include_router(admin_router)
    return router
