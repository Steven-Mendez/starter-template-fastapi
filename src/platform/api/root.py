"""Root service status route for the platform API."""

from __future__ import annotations

from fastapi import APIRouter

root_router = APIRouter(tags=["root"])


@root_router.get("/")
def read_root() -> dict[str, str]:
    """Return a static heartbeat payload identifying the service.

    Useful as a smoke test for routing and TLS termination without
    touching any feature-level code paths.
    """
    return {
        "name": "starter-template-fastapi",
        "message": "FastAPI service is running.",
    }
