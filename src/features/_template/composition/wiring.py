"""Inert wiring stub for the template feature.

The hook is intentionally not registered in ``src/main.py``; copied
features replace it with proper route mounting and container attachment,
following the pattern other production features use (mount routes on
the FastAPI app, attach the container to ``app.state`` under a stable
key).
"""

from __future__ import annotations

from fastapi import FastAPI

from src.features._template.composition.container import TemplateContainer


def register_template(app: FastAPI, container: TemplateContainer) -> None:
    """Placeholder wiring hook for a copied feature.

    Replace this with calls that mount the feature's routers on ``app`` and
    attach ``container`` to ``app.state`` under the feature's stable key.
    """
    raise NotImplementedError("Replace template wiring before registering this feature")
