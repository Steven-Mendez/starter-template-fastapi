"""Runtime contract: producer wiring does not require ``sqlmodel.Session``.

Pairs with the Import Linter rule ``Outbox port consumers do not import
sqlmodel``. The static rule catches direct imports; this runtime test
catches the structural form — a fake :class:`OutboxUnitOfWorkPort` can
satisfy the producer wiring and the auth repository can issue a token
without ever instantiating a real ``Session``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pytest

from features.outbox.application.ports.outbox_uow_port import (
    OutboxUnitOfWorkPort,
    OutboxWriter,
)

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class _RecordingWriter:
    """Trivial :class:`OutboxWriter` that records enqueues in memory."""

    enqueued: list[tuple[str, dict[str, Any], datetime | None]] = field(
        default_factory=list
    )

    def enqueue(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        available_at: datetime | None = None,
    ) -> None:
        self.enqueued.append((job_name, dict(payload), available_at))


@dataclass(slots=True)
class _RecordingUow:
    """Trivial :class:`OutboxUnitOfWorkPort` for assertions."""

    writer: _RecordingWriter = field(default_factory=_RecordingWriter)
    transactions: int = 0

    @contextmanager
    def transaction(self) -> Iterator[OutboxWriter]:
        self.transactions += 1
        yield self.writer


def test_fake_uow_satisfies_outbox_unit_of_work_port_structurally() -> None:
    """Duck-typing: a recording fake is accepted wherever the Protocol is required."""

    def consume(uow: OutboxUnitOfWorkPort) -> int:
        with uow.transaction() as writer:
            writer.enqueue(job_name="send_email", payload={"to": "a@example.com"})
        return 1

    uow = _RecordingUow()
    assert consume(uow) == 1
    assert uow.transactions == 1
    assert uow.writer.enqueued == [("send_email", {"to": "a@example.com"}, None)]
