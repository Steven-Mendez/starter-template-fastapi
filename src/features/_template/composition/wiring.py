from __future__ import annotations

from fastapi import FastAPI

from src.features._template.composition.container import TemplateContainer

# This stub is intentionally inert and is not registered in src/main.py. Copied
# features should replace it with route mounting and container attachment.


def register_template(app: FastAPI, container: TemplateContainer) -> None:
    """Placeholder wiring hook for a copied feature.

    See ``src/features/kanban/composition/wiring.py`` for the canonical pattern.
    """
    raise NotImplementedError("Replace template wiring before registering this feature")
