"""Composition root for the outbox feature.

Builds the engine-scoped repository (used by the relay), exposes a
session-aware :class:`OutboxUnitOfWorkPort` (used by producer
transactions), and constructs the :class:`DispatchPending` use case
the worker schedules on a cron.

The container deliberately does **not** start the relay loop itself —
the web process never runs the relay, only the worker does. The web
process needs only the unit-of-work port so its use cases can write
to ``outbox_messages``; the dispatch use case is built either way so
tests and the worker can drive it without re-instantiating.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.engine import Engine

from features.background_jobs.application.ports.job_queue_port import JobQueuePort
from features.outbox.adapters.outbound.sqlmodel.repository import (
    SQLModelOutboxRepository,
)
from features.outbox.adapters.outbound.sqlmodel.unit_of_work import (
    SQLModelOutboxUnitOfWork,
)
from features.outbox.application.ports.outbox_uow_port import OutboxUnitOfWorkPort
from features.outbox.application.use_cases.dispatch_pending import DispatchPending
from features.outbox.application.use_cases.maintenance.prune_outbox import PruneOutbox
from features.outbox.composition.settings import OutboxSettings


@dataclass(slots=True)
class OutboxContainer:
    """Bundle of the outbox feature's wired components."""

    settings: OutboxSettings
    unit_of_work: OutboxUnitOfWorkPort
    dispatch_pending: DispatchPending
    prune_outbox: PruneOutbox
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
    operations, and the unit-of-work opens producer transactions
    against the same pool. ``job_queue`` is the destination: the
    dispatch use case hands each claimed payload to
    ``job_queue.enqueue``.
    """
    repository = SQLModelOutboxRepository(_engine=engine)
    unit_of_work = SQLModelOutboxUnitOfWork.from_engine(engine)

    dispatch_pending = DispatchPending(
        _repository=repository,
        _job_queue=job_queue,
        _batch_size=settings.claim_batch_size,
        _max_attempts=settings.max_attempts,
        _worker_id=settings.worker_id,
        _retry_base=timedelta(seconds=settings.retry_base_seconds),
        _retry_max=timedelta(seconds=settings.retry_max_seconds),
    )

    prune_outbox = PruneOutbox(_repository=repository)

    def _shutdown() -> None:
        # The container does not own the engine or the job-queue client;
        # those are disposed by their respective owners. Nothing to do
        # here today — kept symmetric with the other features so a future
        # owned resource has an obvious place to land.
        return

    return OutboxContainer(
        settings=settings,
        unit_of_work=unit_of_work,
        dispatch_pending=dispatch_pending,
        prune_outbox=prune_outbox,
        shutdown=_shutdown,
    )
