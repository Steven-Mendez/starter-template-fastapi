from __future__ import annotations

from fastapi import APIRouter

from src.api.dependencies import AppSettingsDep, QueryHandlersDep
from src.api.schemas import HealthPersistence, HealthRead
from src.application.queries import HealthCheckQuery

health_router = APIRouter(tags=["root"])


@health_router.get("/health", response_model=HealthRead)
def health(
    queries: QueryHandlersDep,
    settings: AppSettingsDep,
) -> HealthRead:
    ready = queries.handle_health_check(HealthCheckQuery())
    return HealthRead(
        status="ok" if ready else "degraded",
        persistence=HealthPersistence(
            backend=settings.health_persistence_backend,
            ready=ready,
        ),
    )
