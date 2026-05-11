"""Helpers for stashing the authorization container on ``app.state``.

The platform-level ``require_authorization`` dependency reads only the
port (``app.state.authorization``), but tests sometimes need the whole
container (e.g., to re-run bootstrap). These helpers keep the attribute
name consistent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request

if TYPE_CHECKING:
    from src.features.authorization.composition.container import (
        AuthorizationContainer,
    )


def set_authorization_container(
    app: FastAPI, container: "AuthorizationContainer"
) -> None:
    """Publish ``container`` on ``app.state.authorization_container``."""
    app.state.authorization_container = container


def get_authorization_container(request: Request) -> "AuthorizationContainer":
    """Return the authorization container bound to ``request.app.state``."""
    return request.app.state.authorization_container  # type: ignore[no-any-return]
