"""Application use case for Kanban check readiness behavior."""

from __future__ import annotations

from dataclasses import dataclass

from src.features.kanban.application.queries.health_check import HealthCheckQuery
from src.platform.persistence.readiness import ReadinessProbe


@dataclass(slots=True)
class CheckReadinessUseCase:
    """Delegate readiness reporting to the injected :class:`ReadinessProbe`."""

    readiness: ReadinessProbe

    def execute(self, query: HealthCheckQuery) -> bool:
        """Return whether the underlying dependency reports itself ready."""
        del query
        return self.readiness.is_ready()
