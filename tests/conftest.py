"""One shared ``kanban_store`` for unit + integration; pyramid mix (~70/20/10) in pytest markers."""

from __future__ import annotations

import pytest

from kanban.store import KanbanStore


@pytest.fixture
def kanban_store() -> KanbanStore:
    return KanbanStore()
