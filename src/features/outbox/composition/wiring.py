"""Wiring helpers for the outbox feature."""

from __future__ import annotations

from fastapi import FastAPI

from features.outbox.composition.container import OutboxContainer


def attach_outbox_container(app: FastAPI, container: OutboxContainer) -> None:
    """Publish the :class:`OutboxContainer` on ``app.state``."""
    app.state.outbox_container = container


def get_outbox_container(app: FastAPI) -> OutboxContainer:
    """Return the previously-attached :class:`OutboxContainer`."""
    container = getattr(app.state, "outbox_container", None)
    if container is None:
        raise RuntimeError("OutboxContainer has not been attached to app.state")
    return container
