"""Helpers for storing and retrieving the :class:`UsersContainer` on ``app.state``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, Request

if TYPE_CHECKING:
    from features.users.composition.container import UsersContainer

USERS_CONTAINER_ATTR = "users_container"


def set_users_container(app: FastAPI, container: "UsersContainer") -> None:
    """Attach the ``UsersContainer`` to the FastAPI application state."""
    setattr(app.state, USERS_CONTAINER_ATTR, container)


def get_users_container(request: Request) -> "UsersContainer":
    """Retrieve the ``UsersContainer`` from the current request's application state.

    Raises:
        RuntimeError: If the container was not attached during lifespan startup.
    """
    container = getattr(request.app.state, USERS_CONTAINER_ATTR, None)
    if container is None:
        raise RuntimeError("Users container is not initialized in lifespan")
    return container  # type: ignore[no-any-return]
