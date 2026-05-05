from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.queries.health_check import HealthCheckQuery
from src.platform.persistence.readiness import ReadinessProbe


@dataclass(slots=True)
class CheckReadinessUseCase:
    readiness: ReadinessProbe

    def execute(self, query: HealthCheckQuery) -> bool:
        del query
        return self.readiness.is_ready()
