from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeAlias, cast

from sqlalchemy.engine import Engine

from src.application.ports.clock_port import ClockPort
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.kanban_repository import KanbanRepositoryPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared.readiness import ReadinessProbe
from src.config.settings import AppSettings
from src.infrastructure.adapters.outbound.clock.system_clock import SystemClock
from src.infrastructure.adapters.outbound.id_generator.uuid_id_generator import (
    UUIDIdGenerator,
)
from src.infrastructure.adapters.outbound.persistence import SQLModelKanbanRepository
from src.infrastructure.adapters.outbound.persistence.lifecycle import ClosableResource
from src.infrastructure.adapters.outbound.persistence.sqlmodel.unit_of_work import (
    SqlModelUnitOfWork,
)

UnitOfWorkFactory: TypeAlias = Callable[[], UnitOfWorkPort]
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
    id_gen: IdGeneratorPort
    clock: ClockPort
    shutdown: ShutdownHook


@dataclass(frozen=True, slots=True)
class RuntimeRepositories:
    kanban: ManagedKanbanRepositoryPort


def create_kanban_repository_for_settings(
    settings: AppSettings,
) -> ManagedKanbanRepositoryPort:
    return SQLModelKanbanRepository(settings.postgresql_dsn, create_schema=False)


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
    return _create_sql_runtime_dependencies(repositories)
