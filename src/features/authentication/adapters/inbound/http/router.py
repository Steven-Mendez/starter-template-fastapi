"""Compose public auth and admin routers into one mountable APIRouter."""

from __future__ import annotations

from fastapi import APIRouter

from app_platform.api.operation_ids import feature_operation_id
from features.authentication.adapters.inbound.http.admin import admin_router
from features.authentication.adapters.inbound.http.auth import auth_router


def build_auth_router() -> APIRouter:
    """Return a router that exposes both the public auth and the admin endpoints.

    Mounting only this aggregate keeps ``main.py`` agnostic of the internal
    sub-routes and allows the feature to evolve without touching the app
    composition root. ``generate_unique_id_function`` is propagated for
    consistency even though the aggregate carries no routes of its own.
    """
    router = APIRouter(generate_unique_id_function=feature_operation_id)
    router.include_router(auth_router)
    router.include_router(admin_router)
    return router
