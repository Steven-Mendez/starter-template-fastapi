from __future__ import annotations

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features.kanban.adapters.outbound.persistence.sqlmodel.repository import (
    SessionSQLModelKanbanRepository,
)
from src.features.kanban.tests.contracts.kanban_repository_contract import (
    CONTRACT_SUITE as REPO_SUITE,
)
from src.features.kanban.tests.contracts.query_repository_contract import (
    CONTRACT_SUITE as QUERY_SUITE,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("contract", REPO_SUITE, ids=lambda f: f.__name__)
def test_sqlmodel_repository_contract(contract, postgres_engine: Engine) -> None:  # type: ignore[no-untyped-def]
    def make() -> SessionSQLModelKanbanRepository:
        session = Session(postgres_engine, expire_on_commit=False)
        repo = SessionSQLModelKanbanRepository(session)

        original_save = repo.save

        def commit_save(board) -> None:  # type: ignore[no-untyped-def]
            original_save(board)
            session.commit()

        repo.save = commit_save  # type: ignore[method-assign]

        original_remove = repo.remove

        def commit_remove(board_id: str):  # type: ignore[no-untyped-def]
            result = original_remove(board_id)
            session.commit()
            return result

        repo.remove = commit_remove  # type: ignore[method-assign]
        return repo

    contract(make)


@pytest.mark.parametrize("contract", QUERY_SUITE, ids=lambda f: f.__name__)
def test_sqlmodel_query_contract(contract, postgres_engine: Engine) -> None:  # type: ignore[no-untyped-def]
    def make() -> SessionSQLModelKanbanRepository:
        session = Session(postgres_engine, expire_on_commit=False)
        repo = SessionSQLModelKanbanRepository(session)

        original_save = repo.save

        def commit_save(board) -> None:  # type: ignore[no-untyped-def]
            original_save(board)
            session.commit()

        repo.save = commit_save  # type: ignore[method-assign]
        return repo

    contract(make)
