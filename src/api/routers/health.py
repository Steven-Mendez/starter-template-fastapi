from __future__ import annotations

from fastapi import APIRouter

from src.api.dependencies import AppSettingsDep, CheckReadinessUseCaseDep
from src.api.schemas import HealthPersistence, HealthRead
from src.application.queries import HealthCheckQuery

health_router = APIRouter(tags=["root"])


@health_router.get("/health", response_model=HealthRead)
def health(
    use_case: CheckReadinessUseCaseDep,
    settings: AppSettingsDep,
) -> HealthRead:
    ready = use_case.execute(HealthCheckQuery())
    return HealthRead(
        status="ok" if ready else "degraded",
        persistence=HealthPersistence(
            backend=settings.health_persistence_backend,
            ready=ready,
        ),
    )
