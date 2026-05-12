"""Wiring helpers: mount routes, attach the container, register authz."""

from __future__ import annotations

from fastapi import FastAPI

from src.features._template.adapters.inbound.http.dependencies import (
    attach_template_container as _attach,
)
from src.features._template.adapters.inbound.http.dependencies import (
    get_template_container as _get,
)
from src.features._template.adapters.inbound.http.router import (
    build_template_router,
)
from src.features._template.composition.container import TemplateContainer
from src.features.authorization.application.registry import AuthorizationRegistry


def register_template_authorization(registry: AuthorizationRegistry) -> None:
    """Declare the ``thing`` resource type on the shared authorization registry.

    ``thing`` is a leaf type (no parent walk). The hierarchy is the
    canonical ``owner ⊇ writer ⊇ reader`` triad; mapped actions:

    * ``read`` → reader, writer, owner
    * ``update`` → writer, owner
    * ``delete`` → owner
    """
    registry.register_resource_type(
        "thing",
        actions={
            "read": frozenset({"reader", "writer", "owner"}),
            "update": frozenset({"writer", "owner"}),
            "delete": frozenset({"owner"}),
        },
        hierarchy={
            "reader": frozenset({"reader", "writer", "owner"}),
            "writer": frozenset({"writer", "owner"}),
            "owner": frozenset({"owner"}),
        },
    )


def mount_template_routes(app: FastAPI) -> None:
    """Mount the ``/things`` router on ``app``."""
    app.include_router(build_template_router(), prefix="/things", tags=["things"])


def attach_template_container(app: FastAPI, container: TemplateContainer) -> None:
    """Publish the container on ``app.state``."""
    _attach(app, container)


def get_template_container(app: FastAPI) -> TemplateContainer:
    """Return the previously-attached :class:`TemplateContainer`."""
    return _get(app)
