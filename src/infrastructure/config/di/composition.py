from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeAlias, cast

from sqlalchemy.engine import Engine

from src.application.shared.readiness import ReadinessProbe
from src.application.shared.unit_of_work import UnitOfWork
from src.config.settings import AppSettings
from src.domain.kanban.repository import KanbanRepositoryPort
from src.infrastructure.persistence import (
    InMemoryKanbanRepository,
    SQLiteKanbanRepository,
    SQLModelKanbanRepository,
)
from src.infrastructure.persistence.in_memory_uow import InMemoryUnitOfWork
from src.infrastructure.persistence.lifecycle import ClosableResource
from src.infrastructure.persistence.sqlmodel_uow import SqlModelUnitOfWork

UnitOfWorkFactory: TypeAlias = Callable[[], UnitOfWork]
ShutdownHook: TypeAlias = Callable[[], None]


class ManagedKanbanRepositoryPort(
    KanbanRepositoryPort,
    ReadinessProbe,
    ClosableResource,
    Protocol,
):
    pass


class SqlManagedKanbanRepositoryPort(ManagedKanbanRepositoryPort, Protocol):
    @property
    def engine(self) -> Engine: ...


@dataclass(frozen=True, slots=True)
class RuntimeDependencies:
    repository: ManagedKanbanRepositoryPort
    uow_factory: UnitOfWorkFactory
    readiness_probe: ReadinessProbe
    shutdown: ShutdownHook


def create_repository_for_settings(
    settings: AppSettings,
) -> ManagedKanbanRepositoryPort:
    if settings.repository_backend == "sqlite":
        return SQLiteKanbanRepository(settings.sqlite_path)
    if settings.repository_backend == "postgresql":
        return SQLModelKanbanRepository(settings.postgresql_dsn, create_schema=False)
    return InMemoryKanbanRepository()


def _create_sql_runtime_dependencies(
    repository: SqlManagedKanbanRepositoryPort,
) -> RuntimeDependencies:
    return RuntimeDependencies(
        repository=repository,
        uow_factory=lambda: SqlModelUnitOfWork(repository.engine),
        readiness_probe=repository,
        shutdown=repository.close,
    )


def compose_runtime_dependencies(settings: AppSettings) -> RuntimeDependencies:
    repository = create_repository_for_settings(settings)
    if settings.repository_backend == "inmemory":
        return RuntimeDependencies(
            repository=repository,
            uow_factory=lambda: InMemoryUnitOfWork(repository),
            readiness_probe=repository,
            shutdown=repository.close,
        )
    return _create_sql_runtime_dependencies(
        cast(SqlManagedKanbanRepositoryPort, repository)
    )
