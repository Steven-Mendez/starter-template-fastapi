from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.queries.health_check import HealthCheckQuery


class CheckReadinessUseCasePort(Protocol):
    def execute(self, query: HealthCheckQuery) -> bool: ...
