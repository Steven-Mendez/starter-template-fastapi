from __future__ import annotations

from dataclasses import dataclass

from src.application.queries.health_check import HealthCheckQuery, handle_health_check
from src.application.shared import ReadinessProbe


@dataclass(slots=True)
class CheckReadinessUseCase:
    readiness: ReadinessProbe

    def execute(self, query: HealthCheckQuery) -> bool:
        return handle_health_check(readiness=self.readiness, query=query)
