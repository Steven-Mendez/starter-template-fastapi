"""Query DTO for Kanban health check operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HealthCheckQuery:
    pass
