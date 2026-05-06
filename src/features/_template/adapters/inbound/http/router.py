"""Empty inbound HTTP router for the template feature.

The template stays inert until copied. A real feature should compose
its read/write routers here and map application errors to Problem
Details, mirroring the kanban feature's layout.
"""

from __future__ import annotations

from fastapi import APIRouter


def build_router() -> APIRouter:
    """Return an empty router until a copied feature defines HTTP routes."""
    return APIRouter()
