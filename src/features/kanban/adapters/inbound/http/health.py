"""Readiness route for the Kanban feature."""

from __future__ import annotations

import redis as redis_lib
from fastapi import APIRouter, Response, status

from src.features.kanban.adapters.inbound.http.dependencies import (
    CheckReadinessUseCaseDep,
)
from src.features.kanban.adapters.inbound.http.schemas.health import (
    HealthPersistence,
    HealthRead,
    HealthRedis,
)
from src.features.kanban.application.queries import HealthCheckQuery
from src.platform.api.dependencies.container import AppSettingsDep
from src.platform.api.dependencies.redis_client import AppRedisClientDep

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
def health(
    use_case: CheckReadinessUseCaseDep,
    settings: AppSettingsDep,
    redis_client: AppRedisClientDep,
    response: Response,
) -> HealthRead:
    """Report whether the persistence backend and optional Redis are reachable.

    Returns ``"ok"`` when all configured backends respond successfully and
    ``"degraded"`` otherwise so orchestrators can route traffic away
    without taking the pod offline entirely.
    """
    ready = use_case.execute(HealthCheckQuery())

    redis_health: HealthRedis | None = None
    if settings.auth_redis_url:
        if redis_client is not None:
            try:
                cast_client: redis_lib.Redis = redis_client  # type: ignore[type-arg]
                cast_client.ping()
                redis_health = HealthRedis(configured=True, ready=True)
            except Exception:
                redis_health = HealthRedis(configured=True, ready=False)
        else:
            redis_health = HealthRedis(configured=True, ready=False)

    overall_ok = ready and (redis_health is None or redis_health.ready)
    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthRead(
        status="ok" if overall_ok else "degraded",
        persistence=HealthPersistence(
            backend=settings.health_persistence_backend,
            ready=ready,
        ),
        redis=redis_health,
    )
