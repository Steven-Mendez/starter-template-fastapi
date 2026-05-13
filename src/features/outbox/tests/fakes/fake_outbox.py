"""In-memory :class:`OutboxPort` fake for unit and e2e tests.

The fake mirrors the SQLModel adapter's atomic contract — enqueued
rows are not delivered to the dispatcher until the caller signals
``commit()``; a ``rollback()`` (or a context exit without commit)
drops the pending batch silently. That keeps the existing test
ergonomics intact: tests that previously asserted "an email was
dispatched after this use case ran" only need to call ``commit()``
once at the end (which the real ``write_transaction`` does for
production code).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

PendingEntry = tuple[str, dict[str, Any], datetime | None]


@dataclass(slots=True)
class InMemoryOutboxAdapter:
    """Collect enqueues per transaction; dispatch on ``commit()``.

    A single instance represents *one* transaction's outbox staging
    area. Repository fakes that want to model multiple transactions
    should construct a fresh adapter per transaction.

    The dispatcher is invoked with ``(job_name, payload)`` exactly
    once per committed enqueue, mirroring the relay's interaction
    with ``JobQueuePort.enqueue``. The fake never raises on dispatch:
    tests that want to assert failure should swap in a dispatcher
    that raises and check the resulting state themselves.
    """

    dispatcher: Callable[[str, dict[str, Any]], None]
    _pending: list[PendingEntry] = field(default_factory=list)
    dispatched: list[PendingEntry] = field(default_factory=list)
    rolled_back: list[PendingEntry] = field(default_factory=list)

    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None:
        if available_at is not None and available_at.tzinfo is None:
            raise ValueError("OutboxPort.enqueue: available_at must be timezone-aware")
        self._pending.append((job_name, dict(payload), available_at))

    def commit(self) -> None:
        batch, self._pending = self._pending, []
        for job_name, payload, available_at in batch:
            self.dispatched.append((job_name, payload, available_at))
            self.dispatcher(job_name, payload)

    def rollback(self) -> None:
        batch, self._pending = self._pending, []
        self.rolled_back.extend(batch)


@dataclass(slots=True)
class InlineDispatchOutboxAdapter:
    """E2e-friendly fake that dispatches synchronously at enqueue time.

    Trades the outbox's atomic contract for the ergonomics the existing
    e2e tests rely on (every ``POST /auth/password-reset`` deposits an
    email in the fake email port before the response returns). The
    SQLite-backed e2e harness cannot run the real relay (``FOR UPDATE
    SKIP LOCKED`` is Postgres-only); the atomicity guarantees are
    covered by the testcontainers-backed integration tests instead.
    """

    dispatcher: Callable[[str, dict[str, Any]], None]
    dispatched: list[PendingEntry] = field(default_factory=list)

    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None:
        if available_at is not None and available_at.tzinfo is None:
            raise ValueError("OutboxPort.enqueue: available_at must be timezone-aware")
        copy = dict(payload)
        self.dispatched.append((job_name, copy, available_at))
        self.dispatcher(job_name, copy)
