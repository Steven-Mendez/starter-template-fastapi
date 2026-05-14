"""Integration tests for the outbox retention prune against real Postgres.

Seeds rows with backdated terminal timestamps, runs :class:`PruneOutbox`
via :class:`SQLModelOutboxRepository`, and asserts that:

- Rows older than the configured retention are deleted.
- Recent rows survive.
- The batch-size bound is respected across multiple internal
  iterations.

Marked ``integration``: requires the testcontainers Postgres fixture
``postgres_outbox_engine`` from this directory's ``conftest.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.application.use_cases.maintenance.prune_outbox import PruneOutbox

pytestmark = pytest.mark.integration


def _insert_message(
    session: Session,
    *,
    status: str,
    job_name: str = "send_email",
    delivered_at: datetime | None = None,
    failed_at: datetime | None = None,
) -> None:
    """Insert a single ``outbox_messages`` row at an explicit terminal time."""
    session.execute(
        text(
            """
            INSERT INTO outbox_messages
                (id, job_name, payload, trace_context, available_at, status,
                 attempts, last_error, locked_at, locked_by, created_at,
                 delivered_at, failed_at)
            VALUES
                (:id, :job_name, '{}'::jsonb, '{}'::jsonb, :available_at,
                 :status, 0, NULL, NULL, NULL, :created_at,
                 :delivered_at, :failed_at)
            """
        ),
        {
            "id": uuid4(),
            "job_name": job_name,
            "available_at": datetime.now(UTC),
            "status": status,
            "created_at": datetime.now(UTC),
            "delivered_at": delivered_at,
            "failed_at": failed_at,
        },
    )


def _insert_processed_mark(session: Session, *, processed_at: datetime) -> None:
    session.execute(
        text(
            "INSERT INTO processed_outbox_messages (id, processed_at) "
            "VALUES (:id, :processed_at)"
        ),
        {"id": uuid4(), "processed_at": processed_at},
    )


def _count(engine: Engine, sql: str) -> int:
    with Session(engine, expire_on_commit=False) as session:
        result = session.execute(text(sql)).scalar_one()
        return int(result)


def test_prune_deletes_old_terminal_rows_and_old_marks(
    postgres_outbox_engine: Engine,
) -> None:
    """The spec scenarios: old rows deleted, recent rows survive."""
    now = datetime.now(UTC)
    old_delivered = now - timedelta(days=10)
    recent_delivered = now - timedelta(days=1)
    old_failed = now - timedelta(days=40)
    recent_failed = now - timedelta(days=1)
    old_processed = now - timedelta(hours=1)  # > 2 * 900s = 30 min
    recent_processed = now - timedelta(minutes=5)

    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        for _ in range(50):
            _insert_message(session, status="delivered", delivered_at=old_delivered)
        for _ in range(20):
            _insert_message(session, status="delivered", delivered_at=recent_delivered)
        for _ in range(15):
            _insert_message(session, status="failed", failed_at=old_failed)
        for _ in range(10):
            _insert_message(session, status="failed", failed_at=recent_failed)
        for _ in range(40):
            _insert_processed_mark(session, processed_at=old_processed)
        for _ in range(25):
            _insert_processed_mark(session, processed_at=recent_processed)
        session.commit()

    repository = SQLModelOutboxRepository(_engine=postgres_outbox_engine)
    use_case = PruneOutbox(_repository=repository)
    result = use_case.execute(
        retention_delivered_days=7,
        retention_failed_days=30,
        dedup_retention_seconds=2 * 900,
        batch_size=100,
    )
    from app_platform.shared.result import Ok

    assert isinstance(result, Ok)
    summary = result.value
    assert summary.delivered_deleted == 50
    assert summary.failed_deleted == 15
    assert summary.processed_marks_deleted == 40

    # Recent rows survive.
    assert (
        _count(
            postgres_outbox_engine,
            "SELECT COUNT(*) FROM outbox_messages WHERE status = 'delivered'",
        )
        == 20
    )
    assert (
        _count(
            postgres_outbox_engine,
            "SELECT COUNT(*) FROM outbox_messages WHERE status = 'failed'",
        )
        == 10
    )
    assert (
        _count(
            postgres_outbox_engine,
            "SELECT COUNT(*) FROM processed_outbox_messages",
        )
        == 25
    )


def test_batch_boundary_drains_more_than_one_batch(
    postgres_outbox_engine: Engine,
) -> None:
    """``batch_size + 50`` eligible rows fully drain across iterations."""
    now = datetime.now(UTC)
    old = now - timedelta(days=10)
    eligible_count = 150  # > batch_size (100) so loop must iterate

    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        for _ in range(eligible_count):
            _insert_message(session, status="delivered", delivered_at=old)
        session.commit()

    repository = SQLModelOutboxRepository(_engine=postgres_outbox_engine)
    use_case = PruneOutbox(_repository=repository)
    result = use_case.execute(
        retention_delivered_days=7,
        retention_failed_days=30,
        dedup_retention_seconds=2 * 900,
        batch_size=100,
    )
    from app_platform.shared.result import Ok

    assert isinstance(result, Ok)
    assert result.value.delivered_deleted == eligible_count
    assert _count(postgres_outbox_engine, "SELECT COUNT(*) FROM outbox_messages") == 0


def test_pending_rows_are_not_pruned(postgres_outbox_engine: Engine) -> None:
    """Prune touches only terminal-state rows; ``pending`` rows survive."""
    now = datetime.now(UTC)
    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        # An old delivered row and a pending row of the same age — the
        # pending row has no ``delivered_at``/``failed_at`` so the
        # prune predicates never match it.
        _insert_message(
            session, status="delivered", delivered_at=now - timedelta(days=30)
        )
        _insert_message(session, status="pending")
        session.commit()

    repository = SQLModelOutboxRepository(_engine=postgres_outbox_engine)
    use_case = PruneOutbox(_repository=repository)
    result = use_case.execute(
        retention_delivered_days=7,
        retention_failed_days=30,
        dedup_retention_seconds=2 * 900,
        batch_size=100,
    )
    from app_platform.shared.result import Ok

    assert isinstance(result, Ok)
    assert result.value.delivered_deleted == 1
    assert (
        _count(
            postgres_outbox_engine,
            "SELECT COUNT(*) FROM outbox_messages WHERE status = 'pending'",
        )
        == 1
    )
