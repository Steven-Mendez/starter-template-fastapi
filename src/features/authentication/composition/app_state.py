"""Helpers for storing and retrieving the :class:`AuthContainer` on ``app.state``.

Keeping the container behind explicit setter/getter functions (rather than
plain attribute access scattered across the codebase) means callers don't
need to know the underlying attribute name and benefit from a clear error
message if the container has not been initialised yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request

if TYPE_CHECKING:
    from src.features.authentication.composition.container import AuthContainer

# A single source of truth for the attribute name avoids silent mismatches
# between setter and getter if the name is ever changed.
AUTH_CONTAINER_ATTR = "auth_container"


def set_auth_container(app: FastAPI, container: "AuthContainer") -> None:
    """Attach an ``AuthContainer`` to the FastAPI application state.

    Called during lifespan startup after the container is fully initialised.

    Args:
        app: The FastAPI application instance.
        container: The auth container to attach.
    """
    setattr(app.state, AUTH_CONTAINER_ATTR, container)


def get_auth_container(request: Request) -> "AuthContainer":
    """Retrieve the ``AuthContainer`` from the current request's application state.

    Args:
        request: The current FastAPI ``Request`` object.

    Returns:
        The attached ``AuthContainer``.

    Raises:
        RuntimeError: If the container was not attached during lifespan startup.
    """
    container = getattr(request.app.state, AUTH_CONTAINER_ATTR, None)
    if container is None:
        # A RuntimeError here surfaces misconfigured tests or deployments
        # that skip lifespan startup rather than returning confusing 500s.
        raise RuntimeError("Auth container is not initialized in lifespan")
    return container  # type: ignore[no-any-return]
