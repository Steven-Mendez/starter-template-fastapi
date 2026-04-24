"""Shared store fixture for unit and integration tests."""

from __future__ import annotations

from typing import Generator

import pytest

from src.domain.kanban.repository import KanbanRepositoryPort
from src.infrastructure.persistence.in_memory_repository import InMemoryKanbanRepository
from src.infrastructure.persistence.sqlmodel_repository import SQLModelKanbanRepository


@pytest.fixture(params=["inmemory", "sqlite"])
def kanban_store(
    request: pytest.FixtureRequest,
) -> Generator[KanbanRepositoryPort, None, None]:
    if request.param == "inmemory":
        yield InMemoryKanbanRepository()
    elif request.param == "sqlite":
        # using check_same_thread=False inside the repository implementation for sqlite
        repo = SQLModelKanbanRepository("sqlite:///:memory:")
        yield repo
        repo.close()
