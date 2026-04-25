from __future__ import annotations

from dataclasses import dataclass

from src.application.shared import ReadinessProbe


@dataclass(frozen=True, slots=True)
class HealthCheckQuery:
    pass


def handle_health_check(*, readiness: ReadinessProbe, query: HealthCheckQuery) -> bool:
    del query
    return readiness.is_ready()
