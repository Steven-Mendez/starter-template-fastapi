"""Unit-only fixtures for Kanban command/query setup and test builders."""

from __future__ import annotations

from typing import cast

import pytest

from src.application.commands import KanbanCommandHandlers
from src.application.queries import KanbanQueryHandlers
from src.domain.kanban.repository import KanbanRepository
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository
from src.infrastructure.persistence.in_memory_uow import InMemoryUnitOfWork
from tests.support.kanban_builders import (
    HandlerHarness,
    KanbanBuilderRepository,
    StoreBuilder,
)


@pytest.fixture
def store_builder(kanban_store: KanbanRepository) -> StoreBuilder:
    return StoreBuilder(repository=cast(KanbanBuilderRepository, kanban_store))


@pytest.fixture
def handler_harness() -> HandlerHarness:
    repository = InMemoryKanbanRepository()
    return HandlerHarness(
        commands=KanbanCommandHandlers(uow=InMemoryUnitOfWork(repository)),
        queries=KanbanQueryHandlers(repository=repository),
    )
