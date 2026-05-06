"""Shared pytest fixtures for Kanban feature tests."""

from __future__ import annotations

import pytest

from src.features.kanban.tests.fakes import (
    FakeKanbanWiring,
    InMemoryKanbanRepository,
    build_fake_kanban_wiring,
)


@pytest.fixture
def repository() -> InMemoryKanbanRepository:
    return InMemoryKanbanRepository()


@pytest.fixture
def wiring(repository: InMemoryKanbanRepository) -> FakeKanbanWiring:
    return build_fake_kanban_wiring(repository=repository)
