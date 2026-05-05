from __future__ import annotations

import pytest

from src.features.kanban.tests.contracts.kanban_repository_contract import (
    CONTRACT_SUITE as REPO_SUITE,
)
from src.features.kanban.tests.contracts.query_repository_contract import (
    CONTRACT_SUITE as QUERY_SUITE,
)
from src.features.kanban.tests.fakes import InMemoryKanbanRepository

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("contract", REPO_SUITE, ids=lambda f: f.__name__)
def test_in_memory_kanban_repository_contract(contract) -> None:  # type: ignore[no-untyped-def]
    contract(lambda: InMemoryKanbanRepository())


@pytest.mark.parametrize("contract", QUERY_SUITE, ids=lambda f: f.__name__)
def test_in_memory_query_repository_contract(contract) -> None:  # type: ignore[no-untyped-def]
    contract(lambda: InMemoryKanbanRepository())
