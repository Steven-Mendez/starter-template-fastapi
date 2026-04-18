from __future__ import annotations

from settings import AppSettings
from src.application.ports.repository import KanbanRepository
from src.infrastructure.persistence import (
    InMemoryKanbanRepository,
    SQLiteKanbanRepository,
    SQLModelKanbanRepository,
)


def create_repository_for_settings(settings: AppSettings) -> KanbanRepository:
    if settings.repository_backend == "sqlite":
        return SQLiteKanbanRepository(settings.sqlite_path)
    if settings.repository_backend == "postgresql":
        return SQLModelKanbanRepository(settings.postgresql_dsn, create_schema=False)
    return InMemoryKanbanRepository()
