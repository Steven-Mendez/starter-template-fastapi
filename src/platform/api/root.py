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


@root_router.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    """Process liveness probe.

    Returns 200 as long as the ASGI app can serve a request. Does not
    touch DB, Redis, or any downstream — that's the readiness probe's
    job. Already excluded from tracing and Prometheus metrics in
    ``platform.observability``.
    """
    return {"status": "ok"}
