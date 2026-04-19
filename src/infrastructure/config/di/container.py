from __future__ import annotations

from dataclasses import dataclass

from src.application.queries import KanbanQueryHandlers
from src.config.settings import AppSettings
from src.domain.kanban.repository import KanbanRepository
from src.infrastructure.config.di.composition import (
    UnitOfWorkFactory,
    create_repository_for_settings,
    create_uow_factory_for_settings,
)


@dataclass(slots=True)
class ConfiguredAppContainer:
    settings: AppSettings
    repository: KanbanRepository
    query_handlers: KanbanQueryHandlers
    uow_factory: UnitOfWorkFactory


def build_container(settings: AppSettings) -> ConfiguredAppContainer:
    repository = create_repository_for_settings(settings)
    return ConfiguredAppContainer(
        settings=settings,
        repository=repository,
        query_handlers=KanbanQueryHandlers(repository=repository),
        uow_factory=create_uow_factory_for_settings(settings, repository),
    )
