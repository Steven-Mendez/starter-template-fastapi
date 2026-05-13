"""Glue functions that mount the users feature into a FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from features.users.adapters.inbound.http.router import build_users_router
from features.users.composition.app_state import set_users_container
from features.users.composition.container import UsersContainer


def mount_users_routes(app: FastAPI) -> None:
    """Register every users route on the given FastAPI application.

    Routes are mounted eagerly (before the lifespan event) so the
    generated OpenAPI schema reflects them before the first request.
    """
    app.include_router(build_users_router())


def attach_users_container(app: FastAPI, container: UsersContainer) -> None:
    """Store the users container on ``app.state`` so handlers can resolve it."""
    set_users_container(app, container)
