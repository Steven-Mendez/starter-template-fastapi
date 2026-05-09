"""Glue functions that mount the auth feature into a FastAPI application.

Splitting "mount routes" from "attach container" lets ``main.py`` declare
the OpenAPI schema before the lifespan event has produced the container,
and lets tests register routes against a stub container if needed.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, params

from src.features.auth.adapters.inbound.http.dependencies import get_current_principal
from src.features.auth.adapters.inbound.http.router import build_auth_router
from src.features.auth.composition.app_state import set_auth_container
from src.features.auth.composition.container import AuthContainer


def make_auth_guard() -> list[params.Depends]:
    """Return a FastAPI dependency list that enforces JWT authentication.

    The dependency reads the auth container from ``request.state`` at runtime,
    so no container reference is needed at mount time.
    """
    return [Depends(get_current_principal)]


def mount_auth_routes(app: FastAPI) -> None:
    """Register every auth and admin route on the given FastAPI application.

    Routes are mounted eagerly (before the lifespan event) so the
    generated OpenAPI schema reflects them before the first request and
    routing works during application startup.
    """
    app.include_router(build_auth_router())


def attach_auth_container(app: FastAPI, container: AuthContainer) -> None:
    """Store the auth container on ``app.state`` so handlers can resolve it."""
    set_auth_container(app, container)


def register_auth(app: FastAPI, container: AuthContainer) -> None:
    """Mount the routes and attach the container in a single call.

    Convenience entry point used from ``main.py`` and the test bootstrapping
    code so callers don't have to remember to call both helpers.
    """
    mount_auth_routes(app)
    attach_auth_container(app, container)
