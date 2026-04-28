"""Persistence adapters for Kanban outbound ports."""

from src.infrastructure.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)

__all__ = [
    "SQLModelKanbanRepository",
]
