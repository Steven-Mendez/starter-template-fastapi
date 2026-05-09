"""Run the shared repository contract suites against the real SQLModel adapter.

Each contract function is parametrised so the same scenarios that
validate the in-memory fake also run against PostgreSQL via
testcontainers, catching any drift between the two implementations.
"""

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
    sessions: list[Session] = []

    def make() -> SessionSQLModelKanbanRepository:
        session = Session(postgres_engine, expire_on_commit=False)
        sessions.append(session)
        repo = SessionSQLModelKanbanRepository(session)

        original_save = repo.save

        def commit_save(board) -> None:  # type: ignore[no-untyped-def]
            original_save(board)
            session.commit()

        repo.save = commit_save  # type: ignore[method-assign]

        original_remove = repo.remove

        def commit_remove(board_id, *, actor_id=None):  # type: ignore[no-untyped-def]
            result = original_remove(board_id, actor_id=actor_id)
            session.commit()
            return result

        repo.remove = commit_remove  # type: ignore[method-assign,assignment]
        return repo

    try:
        contract(make)
    finally:
        for session in sessions:
            session.close()


@pytest.mark.parametrize("contract", QUERY_SUITE, ids=lambda f: f.__name__)
def test_sqlmodel_query_contract(contract, postgres_engine: Engine) -> None:  # type: ignore[no-untyped-def]
    sessions: list[Session] = []

    def make() -> SessionSQLModelKanbanRepository:
        session = Session(postgres_engine, expire_on_commit=False)
        sessions.append(session)
        repo = SessionSQLModelKanbanRepository(session)

        original_save = repo.save

        def commit_save(board) -> None:  # type: ignore[no-untyped-def]
            original_save(board)
            session.commit()

        repo.save = commit_save  # type: ignore[method-assign]
        return repo

    try:
        contract(make)
    finally:
        for session in sessions:
            session.close()
