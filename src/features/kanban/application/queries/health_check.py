"""Query DTO for Kanban health check operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HealthCheckQuery:
    """Empty payload for the readiness/health-check use case."""
