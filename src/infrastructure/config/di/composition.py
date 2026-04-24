from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

from src.application.shared.readiness import ReadinessProbe
from src.application.shared.unit_of_work import UnitOfWork
from src.config.settings import AppSettings
from src.domain.kanban.repository import KanbanRepository
from src.infrastructure.persistence import (
    InMemoryKanbanRepository,
    SQLiteKanbanRepository,
    SQLModelKanbanRepository,
)
from src.infrastructure.persistence.in_memory_uow import InMemoryUnitOfWork
from src.infrastructure.persistence.sqlmodel_uow import SqlModelUnitOfWork

UnitOfWorkFactory: TypeAlias = Callable[[], UnitOfWork]
ShutdownHook: TypeAlias = Callable[[], None]


def create_repository_for_settings(settings: AppSettings) -> KanbanRepository:
    if settings.repository_backend == "sqlite":
        return SQLiteKanbanRepository(settings.sqlite_path)
    if settings.repository_backend == "postgresql":
        return SQLModelKanbanRepository(settings.postgresql_dsn, create_schema=False)
    return InMemoryKanbanRepository()


def create_uow_factory_for_settings(
    settings: AppSettings,
    repository: KanbanRepository,
) -> UnitOfWorkFactory:
    if settings.repository_backend == "inmemory":
        if not isinstance(repository, InMemoryKanbanRepository):
            raise RuntimeError("Expected InMemoryKanbanRepository for inmemory backend")
        return lambda: InMemoryUnitOfWork(repository)

    if not isinstance(repository, SQLModelKanbanRepository):
        raise RuntimeError("Expected SQLModelKanbanRepository for SQL backend")
    return lambda: SqlModelUnitOfWork(repository.engine)


def create_readiness_probe_for_settings(
    settings: AppSettings,
    repository: KanbanRepository,
) -> ReadinessProbe:
    if settings.repository_backend == "inmemory":
        if not isinstance(repository, InMemoryKanbanRepository):
            raise RuntimeError("Expected InMemoryKanbanRepository for inmemory backend")
        return repository

    if not isinstance(repository, SQLModelKanbanRepository):
        raise RuntimeError("Expected SQLModelKanbanRepository for SQL backend")
    return repository


def create_shutdown_for_settings(
    settings: AppSettings,
    repository: KanbanRepository,
) -> ShutdownHook:
    if settings.repository_backend == "inmemory":
        if not isinstance(repository, InMemoryKanbanRepository):
            raise RuntimeError("Expected InMemoryKanbanRepository for inmemory backend")
    elif not isinstance(repository, SQLModelKanbanRepository):
        raise RuntimeError("Expected SQLModelKanbanRepository for SQL backend")

    close = getattr(repository, "close", None)
    if not callable(close):
        raise RuntimeError("Configured repository does not expose close()")
    return close
