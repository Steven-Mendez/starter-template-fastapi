"""In-memory :class:`JobQueuePort` for unit and e2e tests.

Records every enqueue call so tests can assert which job got which
payload, without spinning up Redis or running handlers. By default the
fake does *not* validate the job name against a registry — tests that
need that behaviour can set ``known_jobs`` so unknown names raise the
real :class:`UnknownJobError`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from src.features.background_jobs.application.errors import UnknownJobError


@dataclass(frozen=True, slots=True)
class EnqueuedJob:
    """One captured ``JobQueuePort.enqueue`` call."""

    job_name: str
    payload: dict[str, Any]
    run_at: datetime | None = None


@dataclass(slots=True)
class FakeJobQueue:
    """Recording fake of :class:`JobQueuePort` for tests."""

    enqueued: list[EnqueuedJob] = field(default_factory=list)
    known_jobs: set[str] | None = None

    def enqueue(self, job_name: str, payload: dict[str, Any]) -> None:
        self._guard(job_name)
        self.enqueued.append(EnqueuedJob(job_name=job_name, payload=dict(payload)))

    def enqueue_at(
        self,
        job_name: str,
        payload: dict[str, Any],
        run_at: datetime,
    ) -> None:
        self._guard(job_name)
        self.enqueued.append(
            EnqueuedJob(job_name=job_name, payload=dict(payload), run_at=run_at)
        )

    def reset(self) -> None:
        self.enqueued.clear()

    def _guard(self, job_name: str) -> None:
        if self.known_jobs is not None and job_name not in self.known_jobs:
            raise UnknownJobError(job_name=job_name)
