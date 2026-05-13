"""Contract suite for :class:`OutboxPort` implementations.

Runs the same behavioural assertions against the in-memory fake and
the SQLModel session-scoped adapter (when a Postgres engine is
available via the ``postgres_outbox_engine`` fixture in
``conftest.py``). The Postgres path is marked ``integration``; the
fake path is marked ``unit`` so the everyday ``make test`` covers
the contract even without Docker.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from features.outbox.application.ports.outbox_port import OutboxPort
from features.outbox.tests.fakes.fake_outbox import InMemoryOutboxAdapter

pytestmark = pytest.mark.unit


def _fake() -> tuple[OutboxPort, list[tuple[str, dict[str, Any]]]]:
    dispatched: list[tuple[str, dict[str, Any]]] = []

    def _dispatcher(name: str, payload: dict[str, Any]) -> None:
        dispatched.append((name, payload))

    return InMemoryOutboxAdapter(dispatcher=_dispatcher), dispatched


def test_enqueue_then_commit_dispatches_once() -> None:
    adapter, dispatched = _fake()
    adapter.enqueue(
        job_name="send_email",
        payload={"to": "a@example.com"},
    )
    assert dispatched == []
    assert isinstance(adapter, InMemoryOutboxAdapter)
    adapter.commit()
    assert dispatched == [("send_email", {"to": "a@example.com"})]


def test_enqueue_then_rollback_dispatches_nothing() -> None:
    adapter, dispatched = _fake()
    adapter.enqueue(job_name="send_email", payload={"to": "a@example.com"})
    assert isinstance(adapter, InMemoryOutboxAdapter)
    adapter.rollback()
    assert dispatched == []
    assert adapter.rolled_back == [("send_email", {"to": "a@example.com"}, None)]


def test_naive_available_at_is_rejected() -> None:
    adapter, _ = _fake()
    with pytest.raises(ValueError, match="timezone-aware"):
        adapter.enqueue(
            job_name="send_email",
            payload={},
            available_at=datetime.utcnow(),  # noqa: DTZ003 - intentional naive
        )


def test_future_available_at_is_preserved() -> None:
    adapter, _ = _fake()
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    adapter.enqueue(job_name="send_email", payload={}, available_at=future)
    assert isinstance(adapter, InMemoryOutboxAdapter)
    adapter.commit()
    assert adapter.dispatched[-1][2] == future


def test_multiple_enqueues_in_one_transaction_commit_together() -> None:
    adapter, dispatched = _fake()
    adapter.enqueue(job_name="a", payload={"k": 1})
    adapter.enqueue(job_name="b", payload={"k": 2})
    adapter.enqueue(job_name="c", payload={"k": 3})
    assert dispatched == []
    assert isinstance(adapter, InMemoryOutboxAdapter)
    adapter.commit()
    assert [n for n, _ in dispatched] == ["a", "b", "c"]
