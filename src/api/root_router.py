from __future__ import annotations

from fastapi import APIRouter

from src.api.dependencies import AppContainerDep
from src.api.schemas import HealthPersistence, HealthRead
from src.application.queries import HealthCheckQuery

root_router = APIRouter(tags=["root"])


@root_router.get("/")
def read_root() -> dict[str, str]:
    return {
        "name": "starter-template-fastapi",
        "message": "FastAPI service is running.",
    }


@root_router.get("/health", response_model=HealthRead)
def health(
    container: AppContainerDep,
) -> HealthRead:
    ready = container.query_handlers.handle_health_check(HealthCheckQuery())
    return HealthRead(
        status="ok" if ready else "degraded",
        persistence=HealthPersistence(
            backend=container.settings.repository_backend,
            ready=ready,
        ),
    )
