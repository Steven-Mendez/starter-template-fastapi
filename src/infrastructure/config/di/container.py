from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.application.commands import KanbanCommandHandlers, KanbanCommandInputPort
from src.application.queries import KanbanQueryHandlers, KanbanQueryInputPort
from src.config.settings import AppSettings
from src.infrastructure.config.di.composition import (
    RuntimeRepositories,
    ShutdownHook,
    compose_runtime_dependencies,
)

CommandHandlersFactory = Callable[[], KanbanCommandInputPort]


@dataclass(slots=True)
class ConfiguredAppContainer:
    settings: AppSettings
    repositories: RuntimeRepositories
    query_handlers: KanbanQueryInputPort
    command_handlers_factory: CommandHandlersFactory
    shutdown: ShutdownHook

    @property
    def repository(self):
        """Backward-compatible alias to the kanban repository."""
        return self.repositories.kanban


def build_container(settings: AppSettings) -> ConfiguredAppContainer:
    runtime = compose_runtime_dependencies(settings)
    kanban_repository = runtime.repositories.kanban
    return ConfiguredAppContainer(
        settings=settings,
        repositories=runtime.repositories,
        query_handlers=KanbanQueryHandlers(
            repository=kanban_repository,
            readiness=runtime.readiness_probe,
        ),
        command_handlers_factory=lambda: KanbanCommandHandlers(
            uow=runtime.uow_factory(),
            id_gen=runtime.id_gen,
            clock=runtime.clock,
        ),
        shutdown=runtime.shutdown,
    )
