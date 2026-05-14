"""Compose users routers into one mountable APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from app_platform.api.operation_ids import feature_operation_id
from features.users.adapters.inbound.http.admin import admin_router
from features.users.adapters.inbound.http.me import me_router


def build_users_router() -> APIRouter:
    """Return a router exposing the users feature's HTTP endpoints.

    ``generate_unique_id_function`` is propagated for consistency even
    though the aggregate carries no routes of its own.
    """
    router = APIRouter(generate_unique_id_function=feature_operation_id)
    router.include_router(me_router)
    router.include_router(admin_router)
    return router
