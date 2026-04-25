from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeAlias, cast

from sqlalchemy.engine import Engine

from src.application.ports.clock import Clock
from src.application.ports.id_generator import IdGenerator
from src.application.ports.kanban_repository import KanbanRepositoryPort
from src.application.shared.readiness import ReadinessProbe
from src.application.shared.unit_of_work import UnitOfWork
from src.config.settings import AppSettings
from src.infrastructure.adapters.system_clock import SystemClock
from src.infrastructure.adapters.uuid_id_generator import UUIDIdGenerator
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
    repositories: RuntimeRepositories
    uow_factory: UnitOfWorkFactory
    readiness_probe: ReadinessProbe
    id_gen: IdGenerator
    clock: Clock
    shutdown: ShutdownHook


@dataclass(frozen=True, slots=True)
class RuntimeRepositories:
    kanban: ManagedKanbanRepositoryPort


def create_kanban_repository_for_settings(
    settings: AppSettings,
) -> ManagedKanbanRepositoryPort:
    if settings.repository_backend == "sqlite":
        return SQLiteKanbanRepository(settings.sqlite_path)
    if settings.repository_backend == "postgresql":
        return SQLModelKanbanRepository(settings.postgresql_dsn, create_schema=False)
    return InMemoryKanbanRepository()


def create_runtime_repositories(settings: AppSettings) -> RuntimeRepositories:
    return RuntimeRepositories(
        kanban=create_kanban_repository_for_settings(settings),
    )


def create_repository_for_settings(
    settings: AppSettings,
) -> ManagedKanbanRepositoryPort:
    """Backward-compatible helper for callers expecting a single repository."""
    return create_kanban_repository_for_settings(settings)


def _create_sql_runtime_dependencies(
    repositories: RuntimeRepositories,
) -> RuntimeDependencies:
    repository = cast(SqlManagedKanbanRepositoryPort, repositories.kanban)
    return RuntimeDependencies(
        repositories=repositories,
        uow_factory=lambda: SqlModelUnitOfWork(repository.engine),
        readiness_probe=repository,
        id_gen=UUIDIdGenerator(),
        clock=SystemClock(),
        shutdown=repository.close,
    )


def compose_runtime_dependencies(settings: AppSettings) -> RuntimeDependencies:
    repositories = create_runtime_repositories(settings)
    repository = repositories.kanban
    if settings.repository_backend == "inmemory":
        return RuntimeDependencies(
            repositories=repositories,
            uow_factory=lambda: InMemoryUnitOfWork(repository),
            readiness_probe=repository,
            id_gen=UUIDIdGenerator(),
            clock=SystemClock(),
            shutdown=repository.close,
        )
    return _create_sql_runtime_dependencies(repositories)
