"""Shared store fixture for unit and integration tests."""

from __future__ import annotations

import pytest

from kanban.store import KanbanStore


@pytest.fixture
def kanban_store() -> KanbanStore:
    return KanbanStore()
