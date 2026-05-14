"""Integration coverage for the auth → outbox → relay → handler seam.

The auth e2e suite swaps the real outbox for ``InlineDispatchOutboxUnitOfWork``
so the SQLite-backed test engine can still observe email dispatch. That
shortcut leaves the outbox seam itself untested end-to-end — exactly the
gap ``strengthen-test-contracts`` highlights.

This test wires:

- A real Postgres testcontainer (via the session-scoped fixture in
  ``conftest.py`` and a fresh ``public`` schema with all relevant
  tables created).
- The real :class:`SQLModelOutboxUnitOfWork` and
  :class:`SessionSQLModelOutboxAdapter` — the same adapters production
  uses.
- The real :class:`SQLModelOutboxRepository` and
  :class:`DispatchPending` use case for one relay tick.
- A capturing fake :class:`JobQueuePort` that records every enqueue.

The flow under test: ``POST /auth/password-reset`` (via
:class:`RequestPasswordReset`) stages a ``send_email`` outbox row inside
the same transaction as the password-reset internal token; the relay's
next tick dispatches it once and marks the row ``delivered``.

Skipped cleanly without Docker.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Ok
from features.authentication.adapters.outbound.persistence.sqlmodel.models import (
    AuthAuditEventTable,
    AuthInternalTokenTable,
    CredentialTable,
    RefreshTokenTable,
)
from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)
from features.authentication.composition.container import build_auth_container
from features.outbox.adapters.outbound.sqlmodel.models import (
    OutboxMessageTable,
    ProcessedOutboxMessageTable,
)
from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.adapters.outbound.sqlmodel.unit_of_work import (
    SQLModelOutboxUnitOfWork,
)
from features.outbox.application.use_cases.dispatch_pending import DispatchPending
from features.users.adapters.outbound.persistence.sqlmodel.models import UserTable
from features.users.adapters.outbound.persistence.sqlmodel.repository import (
    SessionSQLModelUserRepository,
    SQLModelUserRepository,
)

pytestmark = pytest.mark.integration

_TABLES: list[Any] = [
    UserTable,
    CredentialTable,
    RefreshTokenTable,
    AuthAuditEventTable,
    AuthInternalTokenTable,
    OutboxMessageTable,
    ProcessedOutboxMessageTable,
]


def _load_postgres_container() -> Any:
    try:
        from testcontainers.postgres import (  # type: ignore[import-untyped]
            PostgresContainer,
        )
    except Exception:
        return None
    return PostgresContainer


def _docker_available() -> bool:
    if _load_postgres_container() is None:
        return False
    if os.environ.get("KANBAN_SKIP_TESTCONTAINERS") == "1":
        return False
    try:
        import docker  # type: ignore[import-untyped]

        docker.from_env().ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="module")
def _flow_postgres_url() -> Iterator[str]:
    if not _docker_available():
        pytest.skip("Docker not available for testcontainers")
    container_cls = _load_postgres_container()
    assert container_cls is not None
    with container_cls("postgres:16") as pg:
        yield pg.get_connection_url().replace(
            "postgresql+psycopg2", "postgresql+psycopg"
        )


@pytest.fixture
def flow_engine(_flow_postgres_url: str) -> Iterator[Engine]:
    engine = create_engine(_flow_postgres_url)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    for table in _TABLES:
        table.__table__.create(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_outbox_pending"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_outbox_pending "
                "ON outbox_messages (available_at, id) "
                "WHERE status = 'pending'"
            )
        )
    try:
        yield engine
    finally:
        engine.dispose()


@dataclass(slots=True)
class _CaptureQueue:
    """Fake :class:`JobQueuePort` that records every enqueue."""

    enqueued: list[tuple[str, dict[str, Any]]] = field(default_factory=list)

    def enqueue(self, name: str, payload: dict[str, Any]) -> None:
        self.enqueued.append((name, dict(payload)))

    def enqueue_at(
        self, name: str, payload: dict[str, Any], run_at: datetime
    ) -> None:  # pragma: no cover - not exercised
        raise NotImplementedError


def _make_relay(engine: Engine, queue: _CaptureQueue) -> DispatchPending:
    return DispatchPending(
        _repository=SQLModelOutboxRepository(_engine=engine),
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=5,
        _worker_id="test-worker",
        _retry_base=timedelta(seconds=30),
        _retry_max=timedelta(seconds=900),
    )


def test_password_reset_dispatches_email_via_real_outbox(
    test_settings: AppSettings,
    flow_engine: Engine,
) -> None:
    """End-to-end: register → request reset → relay tick → email dispatched.

    The outbox row is staged by :class:`RequestPasswordReset` inside the
    same transaction as the password-reset token; the relay's next tick
    is what actually hands the ``send_email`` payload to the job queue.
    A regression that ever breaks "outbox seam wired end-to-end" surfaces
    here as a missing ``send_email`` capture.
    """
    settings = test_settings.model_copy(
        update={
            "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
            "auth_return_internal_tokens": True,
            "auth_redis_url": None,
        }
    )

    repo = SQLModelAuthRepository.from_engine(flow_engine)
    users = SQLModelUserRepository(engine=flow_engine)
    outbox_uow = SQLModelOutboxUnitOfWork.from_engine(flow_engine)
    container = build_auth_container(
        settings=settings,
        users=users,
        outbox_uow=outbox_uow,
        user_writer_factory=lambda session: SessionSQLModelUserRepository(
            session=session
        ),
        repository=repo,
    )

    reg = container.register_user.execute(
        email="reset-user@example.com", password="UserPassword123!"
    )
    assert isinstance(reg, Ok)

    # ``request_password_reset`` stages a ``send_email`` outbox row
    # inside the token-issuance transaction.
    reset_result = container.request_password_reset.execute(
        email="reset-user@example.com"
    )
    assert isinstance(reset_result, Ok)

    # Pre-relay: the row is pending; no dispatch has happened yet.
    queue = _CaptureQueue()
    assert queue.enqueued == []
    with Session(flow_engine, expire_on_commit=False) as session:
        pending = session.execute(
            text("SELECT job_name, status FROM outbox_messages")
        ).all()
    assert len(pending) == 1
    assert pending[0].job_name == "send_email"
    assert pending[0].status == "pending"

    # One relay tick MUST dispatch the row and mark it delivered.
    report = _make_relay(flow_engine, queue).execute()
    assert report.dispatched == 1
    assert len(queue.enqueued) == 1
    name, payload = queue.enqueued[0]
    assert name == "send_email"
    # The relay injects ``__outbox_message_id`` for handler-side dedup.
    assert "__outbox_message_id" in payload
    # The email payload preserves the producer-written fields.
    assert payload["to"] == "reset-user@example.com"

    # Post-relay: the row flips to ``delivered`` and a second tick is a no-op.
    with Session(flow_engine, expire_on_commit=False) as session:
        row = session.execute(
            text("SELECT status, delivered_at FROM outbox_messages")
        ).one()
    assert row.status == "delivered"
    assert row.delivered_at is not None

    second = _make_relay(flow_engine, queue).execute()
    assert second.dispatched == 0
    assert len(queue.enqueued) == 1

    container.shutdown()
