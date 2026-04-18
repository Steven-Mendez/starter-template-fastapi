from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from dependencies import AppContainer, get_app_container
from src.application.queries import HealthCheckQuery

root_router = APIRouter(tags=["root"])


@root_router.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": "starter-template-fastapi",
        "message": "FastAPI service is running.",
    }


@root_router.get("/health")
def health(
    container: Annotated[AppContainer, Depends(get_app_container)],
) -> dict[str, object]:
    ready = container.query_handlers.handle_health_check(HealthCheckQuery())
    return {
        "status": "ok" if ready else "degraded",
        "persistence": {
            "backend": container.settings.repository_backend,
            "ready": ready,
        },
    }
