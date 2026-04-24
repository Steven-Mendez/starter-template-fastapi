from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from src.application.commands import KanbanCommandHandlers, KanbanCommandInputPort
from src.application.queries import KanbanQueryHandlers, KanbanQueryInputPort
from src.config.settings import AppSettings
from src.domain.kanban.repository import KanbanRepositoryPort
from src.infrastructure.config.di.composition import (
    ShutdownHook,
    create_readiness_probe_for_settings,
    create_repository_for_settings,
    create_shutdown_for_settings,
    create_uow_factory_for_settings,
)

CommandHandlersFactory = Callable[[], KanbanCommandInputPort]


@dataclass(slots=True)
class ConfiguredAppContainer:
    settings: AppSettings
    repository: KanbanRepositoryPort
    query_handlers: KanbanQueryInputPort
    command_handlers_factory: CommandHandlersFactory
    shutdown: ShutdownHook


def build_container(settings: AppSettings) -> ConfiguredAppContainer:
    repository = create_repository_for_settings(settings)
    uow_factory = create_uow_factory_for_settings(settings, repository)
    readiness_probe = create_readiness_probe_for_settings(settings, repository)
    shutdown = create_shutdown_for_settings(settings, repository)
    return ConfiguredAppContainer(
        settings=settings,
        repository=repository,
        query_handlers=KanbanQueryHandlers(
            repository=repository,
            readiness=readiness_probe,
        ),
        command_handlers_factory=lambda: KanbanCommandHandlers(uow=uow_factory()),
        shutdown=shutdown,
    )
