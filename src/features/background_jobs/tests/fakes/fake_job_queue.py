"""In-memory :class:`JobQueuePort` for unit and e2e tests.

Records every enqueue call so tests can assert which job got which
payload, without spinning up Redis or running handlers.

Mirrors the production :class:`InProcessJobQueueAdapter`: by default the
fake validates job names against ``known_jobs`` and raises
:class:`UnknownJobError` for anything unregistered. Callers that want a
wide-open fake (e.g. ad-hoc capture of enqueues without a registry) opt
into permissive mode explicitly with ``permissive=True``. Defaulting
to strict prevents tests from green-lighting a production
:class:`UnknownJobError` regression.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from features.background_jobs.application.errors import UnknownJobError


@dataclass(frozen=True, slots=True)
class EnqueuedJob:
    """One captured ``JobQueuePort.enqueue`` call."""

    job_name: str
    payload: dict[str, Any]
    run_at: datetime | None = None


@dataclass(slots=True)
class FakeJobQueue:
    """Recording fake of :class:`JobQueuePort` for tests.

    Pass ``known_jobs`` to validate against a registry-like set, or
    ``permissive=True`` to accept any job name.
    """

    known_jobs: set[str] | None = None
    permissive: bool = False
    enqueued: list[EnqueuedJob] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.known_jobs is None and not self.permissive:
            raise ValueError(
                "FakeJobQueue requires either known_jobs or permissive=True; "
                "the strict default mirrors InProcessJobQueueAdapter so a "
                "missing registry binding cannot hide in tests."
            )

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
