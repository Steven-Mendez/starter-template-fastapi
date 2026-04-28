from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.application.ports.clock_port import ClockPort
from src.application.ports.id_generator_port import IdGeneratorPort
from src.application.ports.kanban_query_repository import KanbanQueryRepositoryPort
from src.application.ports.unit_of_work_port import UnitOfWorkPort
from src.application.shared.readiness import ReadinessProbe
from src.config.settings import AppSettings
from src.infrastructure.adapters.outbound.query.kanban_query_repository_view import (
    KanbanQueryRepositoryView,
)
from src.infrastructure.config.di.composition import (
    ManagedKanbanRepositoryPort,
    RuntimeRepositories,
    ShutdownHook,
    compose_runtime_dependencies,
)

UnitOfWorkFactory = Callable[[], UnitOfWorkPort]


@dataclass(slots=True)
class ConfiguredAppContainer:
    settings: AppSettings
    repositories: RuntimeRepositories
    query_repository: KanbanQueryRepositoryPort
    uow_factory: UnitOfWorkFactory
    id_gen: IdGeneratorPort
    clock: ClockPort
    readiness_probe: ReadinessProbe
    shutdown: ShutdownHook

    @property
    def repository(self) -> ManagedKanbanRepositoryPort:
        """Backward-compatible alias to the kanban repository."""
        return self.repositories.kanban


def build_container(settings: AppSettings) -> ConfiguredAppContainer:
    runtime = compose_runtime_dependencies(settings)
    kanban_repository = runtime.repositories.kanban
    query_repository = KanbanQueryRepositoryView(kanban_repository)
    return ConfiguredAppContainer(
        settings=settings,
        repositories=runtime.repositories,
        query_repository=query_repository,
        uow_factory=runtime.uow_factory,
        id_gen=runtime.id_gen,
        clock=runtime.clock,
        readiness_probe=runtime.readiness_probe,
        shutdown=runtime.shutdown,
    )
