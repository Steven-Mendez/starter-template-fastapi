"""Unit tests for ``SQLModelUserRegistrarAdapter``."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

from src.features.auth.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    RefreshTokenTable,
    UserTable,
)
from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from src.features.auth.adapters.outbound.user_registrar import (
    SQLModelUserRegistrarAdapter,
)
from src.features.auth.application.crypto import PasswordService
from src.features.auth.application.use_cases.auth.register_user import RegisterUser
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit

_SCHEMA: list[Any] = [
    UserTable,
    RefreshTokenTable,
    AuthAuditEventTable,
    AuthInternalTokenTable,
]


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
def adapter(engine: Engine, test_settings: AppSettings) -> SQLModelUserRegistrarAdapter:
    repository = SQLModelAuthRepository.from_engine(engine)
    register_user = RegisterUser(
        _repository=repository,
        _password_service=PasswordService(),
        _settings=test_settings,
    )
    return SQLModelUserRegistrarAdapter(
        repository=repository, register_user=register_user
    )


def test_first_call_creates_a_new_user(
    adapter: SQLModelUserRegistrarAdapter,
) -> None:
    user_id = adapter.register_or_lookup(
        email="alice@example.com", password="GoodPassword123!"
    )
    assert user_id is not None


def test_second_call_returns_the_same_user_id(
    adapter: SQLModelUserRegistrarAdapter,
) -> None:
    first = adapter.register_or_lookup(
        email="alice@example.com", password="GoodPassword123!"
    )
    second = adapter.register_or_lookup(
        email="alice@example.com", password="GoodPassword123!"
    )
    assert first == second


def test_email_is_normalised(adapter: SQLModelUserRegistrarAdapter) -> None:
    first = adapter.register_or_lookup(
        email="alice@example.com", password="GoodPassword123!"
    )
    second = adapter.register_or_lookup(
        email="  ALICE@Example.com ", password="GoodPassword123!"
    )
    assert first == second
