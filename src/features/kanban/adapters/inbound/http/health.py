"""Liveness and readiness probes for the service.

Two distinct probe endpoints allow orchestrators (Kubernetes, ECS, etc.) to
distinguish process-level failures from dependency failures:

* ``GET /health/live`` — liveness probe: returns 200 as long as the process
  is running. No external dependencies are checked, so a restart is only
  triggered by process crashes, not by a slow database.

* ``GET /health/ready`` — readiness probe: returns 200 when all configured
  backends (DB, Redis, auth principal cache) are reachable and correctly
  configured. Returns 503 when degraded so the load balancer can stop
  routing traffic without restarting the pod.

* ``GET /health`` — backward-compatible alias for ``/health/ready``.
"""

from __future__ import annotations

import redis as redis_lib
from fastapi import APIRouter, Request, Response, status

from src.features.kanban.adapters.inbound.http.dependencies import (
    CheckReadinessUseCaseDep,
)
from src.features.kanban.adapters.inbound.http.schemas.health import (
    HealthAuth,
    HealthLive,
    HealthPersistence,
    HealthRead,
    HealthRedis,
)
from src.features.kanban.application.queries import HealthCheckQuery
from src.platform.api.dependencies.container import AppSettingsDep
from src.platform.api.dependencies.redis_client import AppRedisClientDep

health_router = APIRouter(tags=["health"])


@health_router.get("/health/live", response_model=HealthLive)
def liveness() -> HealthLive:
    """Liveness probe — confirms the process is running.

    No external dependencies are checked. Orchestrators should use this
    probe to decide whether to restart the container; use ``/health/ready``
    to decide whether to route traffic.
    """
    return HealthLive()


def _readiness(
    request: Request,
    use_case: CheckReadinessUseCaseDep,
    settings: AppSettingsDep,
    redis_client: AppRedisClientDep,
    response: Response,
) -> HealthRead:
    """Shared readiness logic used by both /health/ready and /health."""
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

    auth_container = getattr(request.app.state, "auth_container", None)
    principal_cache_ready = (
        auth_container is not None
        and getattr(auth_container, "principal_cache", None) is not None
    )
    rate_limiter_ready = (
        redis_health.ready
        if redis_health is not None
        else not settings.auth_require_distributed_rate_limit
    )
    auth_health = HealthAuth(
        jwt_secret_configured=bool(settings.auth_jwt_secret_key),
        principal_cache_ready=principal_cache_ready,
        rate_limiter_backend="redis" if settings.auth_redis_url else "in_memory",
        rate_limiter_ready=rate_limiter_ready,
    )

    overall_ok = (
        ready
        and auth_health.jwt_secret_configured
        and auth_health.principal_cache_ready
        and auth_health.rate_limiter_ready
        and (redis_health is None or redis_health.ready)
    )
    if not overall_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthRead(
        status="ok" if overall_ok else "degraded",
        persistence=HealthPersistence(
            backend=settings.health_persistence_backend,
            ready=ready,
        ),
        auth=auth_health,
        redis=redis_health,
    )


@health_router.get("/health/ready", response_model=HealthRead)
def readiness(
    request: Request,
    use_case: CheckReadinessUseCaseDep,
    settings: AppSettingsDep,
    redis_client: AppRedisClientDep,
    response: Response,
) -> HealthRead:
    """Readiness probe — checks all configured backends.

    Returns HTTP 200 when all backends are reachable and ``status: ok``.
    Returns HTTP 503 with ``status: degraded`` when any backend is down.
    Load balancers should stop routing traffic on 503; orchestrators should
    NOT restart on 503 alone (use ``/health/live`` to trigger restarts).
    """
    return _readiness(request, use_case, settings, redis_client, response)


@health_router.get("/health", response_model=HealthRead)
def health(
    request: Request,
    use_case: CheckReadinessUseCaseDep,
    settings: AppSettingsDep,
    redis_client: AppRedisClientDep,
    response: Response,
) -> HealthRead:
    """Readiness probe — backward-compatible alias for ``/health/ready``.

    Prefer ``/health/ready`` in new deployments for semantic clarity.
    """
    return _readiness(request, use_case, settings, redis_client, response)
