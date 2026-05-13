"""Integration coverage for :class:`SQLModelOutboxUnitOfWork`.

Asserts the transport-agnostic seam producers consume:

- The yielded writer's ``enqueue`` stages a row that becomes visible
  to the relay only after the surrounding ``transaction()`` commits.
- An exception inside the context rolls back the transaction so the
  row never persists.
- The writer exposes its underlying session so SQLModel-aware
  producer adapters (e.g. the auth repository) can attach their own
  writes to the same transaction.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlmodel import Session

from features.outbox.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelOutboxAdapter,
)
from features.outbox.adapters.outbound.sqlmodel.unit_of_work import (
    SQLModelOutboxUnitOfWork,
)

pytestmark = pytest.mark.integration


def _count_pending(engine: Engine) -> int:
    with Session(engine) as session:
        row = session.execute(
            sa.text("SELECT count(*) FROM outbox_messages WHERE status = 'pending'")
        ).one()
        return int(row[0])


def test_enqueue_commits_when_transaction_exits_cleanly(
    postgres_outbox_engine: Engine,
) -> None:
    uow = SQLModelOutboxUnitOfWork.from_engine(postgres_outbox_engine)

    with uow.transaction() as writer:
        writer.enqueue(job_name="send_email", payload={"to": "a@example.com"})

    assert _count_pending(postgres_outbox_engine) == 1


def _enqueue_then_raise(
    uow: SQLModelOutboxUnitOfWork, *, to: str, message: str
) -> None:
    """Enqueue inside a transaction, then raise — for rollback assertions."""
    with uow.transaction() as writer:
        writer.enqueue(job_name="send_email", payload={"to": to})
        raise RuntimeError(message)


def test_enqueue_rolls_back_when_transaction_raises(
    postgres_outbox_engine: Engine,
) -> None:
    uow = SQLModelOutboxUnitOfWork.from_engine(postgres_outbox_engine)

    with pytest.raises(RuntimeError, match="producer-error"):
        _enqueue_then_raise(uow, to="a@example.com", message="producer-error")

    assert _count_pending(postgres_outbox_engine) == 0


def test_subsequent_transaction_after_rollback_is_unaffected(
    postgres_outbox_engine: Engine,
) -> None:
    uow = SQLModelOutboxUnitOfWork.from_engine(postgres_outbox_engine)

    with pytest.raises(RuntimeError):
        _enqueue_then_raise(uow, to="a@example.com", message="boom")

    with uow.transaction() as writer:
        writer.enqueue(job_name="send_email", payload={"to": "b@example.com"})

    assert _count_pending(postgres_outbox_engine) == 1


def test_writer_exposes_session_for_sqlmodel_aware_producers(
    postgres_outbox_engine: Engine,
) -> None:
    """The SQL writer exposes its session so producers can share the transaction."""
    uow = SQLModelOutboxUnitOfWork.from_engine(postgres_outbox_engine)

    with uow.transaction() as writer:
        assert isinstance(writer, SessionSQLModelOutboxAdapter)
        assert isinstance(writer.session, Session)
        writer.enqueue(job_name="send_email", payload={"to": "c@example.com"})

    assert _count_pending(postgres_outbox_engine) == 1
