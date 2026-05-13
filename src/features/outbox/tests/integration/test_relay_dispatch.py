"""End-to-end relay dispatch against a real PostgreSQL.

Covers the wire-level contract:
- A pending row is dispatched and marked ``dispatched``.
- A failing dispatch increments ``attempts`` and reschedules
  ``available_at``.
- Reaching ``max_attempts`` flips the row to ``failed``.

Marked ``integration``: relies on a testcontainers Postgres started
by the session-scoped fixture in ``conftest.py``. Skipped on hosts
without Docker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelOutboxAdapter,
)
from features.outbox.adapters.outbound.sqlmodel.models import OutboxMessageTable
from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.application.use_cases.dispatch_pending import DispatchPending

pytestmark = pytest.mark.integration


@dataclass(slots=True)
class _StubQueue:
    enqueued: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    raise_on: set[str] = field(default_factory=set)

    def enqueue(self, name: str, payload: dict[str, Any]) -> None:
        self.enqueued.append((name, payload))
        if name in self.raise_on:
            raise RuntimeError(f"forced failure for {name}")

    def enqueue_at(
        self, name: str, payload: dict[str, Any], run_at: datetime
    ) -> None:  # pragma: no cover - not exercised
        raise NotImplementedError


def _seed(engine: Engine, *, job_name: str = "send_email") -> None:
    with Session(engine, expire_on_commit=False) as session:
        SessionSQLModelOutboxAdapter(_session=session).enqueue(
            job_name=job_name, payload={"to": "x@example.com"}
        )
        session.commit()


def _all_rows(engine: Engine) -> list[OutboxMessageTable]:
    with Session(engine, expire_on_commit=False) as session:
        return list(session.exec(_select_all()).all())


def _select_all() -> Any:
    from sqlmodel import select

    return select(OutboxMessageTable).order_by("created_at")


def test_pending_row_is_dispatched(postgres_outbox_engine: Engine) -> None:
    _seed(postgres_outbox_engine)
    queue = _StubQueue()
    use_case = DispatchPending(
        _repository=SQLModelOutboxRepository(_engine=postgres_outbox_engine),
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=5,
        _worker_id="test-worker",
    )
    report = use_case.execute()
    assert report.dispatched == 1
    assert queue.enqueued == [("send_email", {"to": "x@example.com"})]
    rows = _all_rows(postgres_outbox_engine)
    assert len(rows) == 1
    assert rows[0].status == "dispatched"
    assert rows[0].dispatched_at is not None
    assert rows[0].locked_at is None  # released after marking dispatched


def test_transient_failure_increments_attempts_and_reschedules(
    postgres_outbox_engine: Engine,
) -> None:
    _seed(postgres_outbox_engine, job_name="boom")
    queue = _StubQueue(raise_on={"boom"})
    use_case = DispatchPending(
        _repository=SQLModelOutboxRepository(_engine=postgres_outbox_engine),
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=5,
        _worker_id="test-worker",
    )
    report = use_case.execute()
    assert report.retried == 1
    rows = _all_rows(postgres_outbox_engine)
    assert rows[0].status == "pending"
    assert rows[0].attempts == 1
    assert rows[0].last_error is not None
    assert rows[0].available_at > datetime.now(timezone.utc)


def test_exhausted_attempts_flips_to_failed(
    postgres_outbox_engine: Engine,
) -> None:
    _seed(postgres_outbox_engine, job_name="boom")
    repo = SQLModelOutboxRepository(_engine=postgres_outbox_engine)
    queue = _StubQueue(raise_on={"boom"})
    use_case = DispatchPending(
        _repository=repo,
        _job_queue=queue,
        _batch_size=10,
        _max_attempts=2,
        _worker_id="test-worker",
    )
    # First tick: attempts becomes 1, still pending.
    use_case.execute()
    # Force the row back to claim-eligible immediately.
    with Session(postgres_outbox_engine, expire_on_commit=False) as session:
        row = session.exec(_select_all()).one()
        row.available_at = datetime.now(timezone.utc)
        session.add(row)
        session.commit()
    # Second tick: attempts would be 2 (== max), so the row flips to failed.
    report = use_case.execute()
    assert report.failed == 1
    rows = _all_rows(postgres_outbox_engine)
    assert rows[0].status == "failed"
    assert rows[0].attempts == 2
