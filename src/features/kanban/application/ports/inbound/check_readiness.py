"""Inbound use-case protocol for Kanban check readiness operations."""

from __future__ import annotations

from typing import Protocol

from src.features.kanban.application.queries.health_check import HealthCheckQuery


class CheckReadinessUseCasePort(Protocol):
    """Port for ``GET /health/ready``; ``True`` only when dependencies are usable."""

    def execute(self, query: HealthCheckQuery) -> bool: ...
