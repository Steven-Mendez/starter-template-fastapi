"""HTTP-level dependency helpers for the template feature."""

from __future__ import annotations

from fastapi import FastAPI

from src.features._template.composition.container import TemplateContainer

_APP_STATE_KEY = "template_container"


def attach_template_container(app: FastAPI, container: TemplateContainer) -> None:
    """Publish the container on ``app.state`` for the inbound dependencies to read."""
    setattr(app.state, _APP_STATE_KEY, container)


def get_template_container(app: FastAPI) -> TemplateContainer:
    """Return the previously-attached :class:`TemplateContainer`."""
    container = getattr(app.state, _APP_STATE_KEY, None)
    if container is None:
        raise RuntimeError("Template container has not been attached to app.state.")
    return container
