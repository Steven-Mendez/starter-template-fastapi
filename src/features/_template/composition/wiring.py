"""Inert wiring stub for the template feature.

The hook is intentionally not registered in ``src/main.py``; copied
features replace it with proper route mounting and container
attachment, following the kanban feature's pattern.
"""

from __future__ import annotations

from fastapi import FastAPI

from src.features._template.composition.container import TemplateContainer


def register_template(app: FastAPI, container: TemplateContainer) -> None:
    """Placeholder wiring hook for a copied feature.

    See ``src/features/kanban/composition/wiring.py`` for the canonical pattern.
    """
    raise NotImplementedError("Replace template wiring before registering this feature")
