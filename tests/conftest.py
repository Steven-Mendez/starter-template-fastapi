"""One shared ``kanban_store`` for unit + integration; prefer a testing pyramid (many unit, fewer integration, minimal e2e), often approximated with Fibonacci-style ratios such as 5:3:2 for new feature slices (φ-based balance)."""

from __future__ import annotations

import pytest

from kanban.store import KanbanStore


@pytest.fixture
def kanban_store() -> KanbanStore:
    return KanbanStore()
