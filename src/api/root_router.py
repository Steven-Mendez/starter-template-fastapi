from __future__ import annotations

from fastapi import APIRouter

from src.api.dependencies import AppSettingsDep, QueryHandlersDep
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
    settings: AppSettingsDep,
    queries: QueryHandlersDep,
) -> HealthRead:
    ready = queries.handle_health_check(HealthCheckQuery())
    return HealthRead(
        status="ok" if ready else "degraded",
        persistence=HealthPersistence(
            backend=settings.repository_backend,
            ready=ready,
        ),
    )
