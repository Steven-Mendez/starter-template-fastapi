"""Readiness route for the Kanban feature."""

from __future__ import annotations

from fastapi import APIRouter

from src.features.kanban.adapters.inbound.http.dependencies import (
    CheckReadinessUseCaseDep,
)
from src.features.kanban.adapters.inbound.http.schemas.health import (
    HealthPersistence,
    HealthRead,
)
from src.features.kanban.application.queries import HealthCheckQuery
from src.platform.api.dependencies.container import AppSettingsDep

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
def health(
    use_case: CheckReadinessUseCaseDep,
    settings: AppSettingsDep,
) -> HealthRead:
    """Report whether the persistence backend is reachable.

    Returns ``"ok"`` when the underlying store responds successfully and
    ``"degraded"`` otherwise so orchestrators can route traffic away
    without taking the pod offline entirely.
    """
    ready = use_case.execute(HealthCheckQuery())
    return HealthRead(
        status="ok" if ready else "degraded",
        persistence=HealthPersistence(
            backend=settings.health_persistence_backend,
            ready=ready,
        ),
    )
