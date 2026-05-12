"""Unit tests for ``SQLModelUserRegistrarAdapter``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.users.adapters.outbound.persistence.sqlmodel.models import (
    UserTable,
)
from src.features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelUserRepository,
)
from src.features.users.adapters.outbound.user_registrar import (
    SQLModelUserRegistrarAdapter,
)

pytestmark = pytest.mark.unit

_SCHEMA: list[Any] = [UserTable]


class _RecordingCredentialWriter:
    """In-memory ``CredentialWriterPort`` capturing each write."""

    def __init__(self) -> None:
        self.writes: list[tuple[UUID, str]] = []

    def set_initial_password(self, *, user_id: UUID, password: str) -> None:
        self.writes.append((user_id, password))


@pytest.fixture
def engine() -> Iterator[Engine]:
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in _SCHEMA:
        table.__table__.create(eng, checkfirst=True)
    yield eng
    eng.dispose()


@pytest.fixture
def credential_writer() -> _RecordingCredentialWriter:
    return _RecordingCredentialWriter()


@pytest.fixture
def adapter(
    engine: Engine, credential_writer: _RecordingCredentialWriter
) -> SQLModelUserRegistrarAdapter:
    return SQLModelUserRegistrarAdapter(
        users=SQLModelUserRepository(engine=engine),
        credential_writer=credential_writer,
    )


def test_first_call_creates_a_new_user(
    adapter: SQLModelUserRegistrarAdapter,
    credential_writer: _RecordingCredentialWriter,
) -> None:
    user_id = adapter.register_or_lookup(
        email="alice@example.com", password="GoodPassword123!"
    )
    assert user_id is not None
    assert credential_writer.writes == [(user_id, "GoodPassword123!")]


def test_second_call_returns_the_same_user_id(
    adapter: SQLModelUserRegistrarAdapter,
    credential_writer: _RecordingCredentialWriter,
) -> None:
    first = adapter.register_or_lookup(
        email="alice@example.com", password="GoodPassword123!"
    )
    second = adapter.register_or_lookup(
        email="alice@example.com", password="GoodPassword123!"
    )
    assert first == second
    # The credential is only written when the user is newly created.
    assert len(credential_writer.writes) == 1


def test_email_is_normalised(adapter: SQLModelUserRegistrarAdapter) -> None:
    first = adapter.register_or_lookup(
        email="alice@example.com", password="GoodPassword123!"
    )
    second = adapter.register_or_lookup(
        email="  ALICE@Example.com ", password="GoodPassword123!"
    )
    assert first == second
