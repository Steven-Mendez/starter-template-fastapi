"""Persistence adapters for Kanban outbound ports."""

from src.features.kanban.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelKanbanRepository,
)

__all__ = [
    "SQLModelKanbanRepository",
]
