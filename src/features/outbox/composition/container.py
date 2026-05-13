"""Composition root for the outbox feature.

Builds the engine-scoped repository (used by the relay), exposes a
factory for the session-scoped :class:`OutboxPort` (used by producer
transactions), and constructs the :class:`DispatchPending` use case
the worker schedules on a cron.

The container deliberately does **not** start the relay loop itself —
the web process never runs the relay, only the worker does. The web
process needs only the session-scoped factory so its use cases can
write to ``outbox_messages``; the dispatch use case is built either
way so tests and the worker can drive it without re-instantiating.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features.background_jobs.application.ports.job_queue_port import JobQueuePort
from src.features.outbox.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelOutboxAdapter,
)
from src.features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from src.features.outbox.application.ports.outbox_port import OutboxPort
from src.features.outbox.application.use_cases.dispatch_pending import DispatchPending
from src.features.outbox.composition.settings import OutboxSettings

# A callable producers use to construct an outbox port bound to *their*
# session. Keeping it as a Callable (not the adapter type) lets a future
# adapter (e.g. an in-memory test double for an integration test) plug
# in without changing producer code.
SessionScopedOutboxFactory = Callable[[Session], OutboxPort]


@dataclass(slots=True)
class OutboxContainer:
    """Bundle of the outbox feature's wired components."""

    settings: OutboxSettings
    session_scoped_factory: SessionScopedOutboxFactory
    dispatch_pending: DispatchPending
    shutdown: Callable[[], None]


def build_outbox_container(
    settings: OutboxSettings,
    *,
    engine: Engine,
    job_queue: JobQueuePort,
) -> OutboxContainer:
    """Build the outbox feature's container.

    ``engine`` is the shared SQLModel engine — the relay's repository
    opens short transactions against it for the claim and the mark
    operations. ``job_queue`` is the destination: the dispatch use
    case hands each claimed payload to ``job_queue.enqueue``.
    """
    repository = SQLModelOutboxRepository(_engine=engine)

    def _session_scoped_factory(session: Session) -> OutboxPort:
        return SessionSQLModelOutboxAdapter(_session=session)

    dispatch_pending = DispatchPending(
        _repository=repository,
        _job_queue=job_queue,
        _batch_size=settings.claim_batch_size,
        _max_attempts=settings.max_attempts,
        _worker_id=settings.worker_id,
    )

    def _shutdown() -> None:
        # The container does not own the engine or the job-queue client;
        # those are disposed by their respective owners. Nothing to do
        # here today — kept symmetric with the other features so a future
        # owned resource has an obvious place to land.
        return

    return OutboxContainer(
        settings=settings,
        session_scoped_factory=_session_scoped_factory,
        dispatch_pending=dispatch_pending,
        shutdown=_shutdown,
    )
