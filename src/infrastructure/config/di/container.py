from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.application.commands import KanbanCommandHandlers, KanbanCommandInputPort
from src.application.queries import KanbanQueryHandlers, KanbanQueryInputPort
from src.config.settings import AppSettings
from src.infrastructure.config.di.composition import (
    ManagedKanbanRepositoryPort,
    ShutdownHook,
    compose_runtime_dependencies,
)

CommandHandlersFactory = Callable[[], KanbanCommandInputPort]


@dataclass(slots=True)
class ConfiguredAppContainer:
    settings: AppSettings
    repository: ManagedKanbanRepositoryPort
    query_handlers: KanbanQueryInputPort
    command_handlers_factory: CommandHandlersFactory
    shutdown: ShutdownHook


def build_container(settings: AppSettings) -> ConfiguredAppContainer:
    runtime = compose_runtime_dependencies(settings)
    return ConfiguredAppContainer(
        settings=settings,
        repository=runtime.repository,
        query_handlers=KanbanQueryHandlers(
            repository=runtime.repository,
            readiness=runtime.readiness_probe,
        ),
        command_handlers_factory=lambda: KanbanCommandHandlers(
            uow=runtime.uow_factory()
        ),
        shutdown=runtime.shutdown,
    )
