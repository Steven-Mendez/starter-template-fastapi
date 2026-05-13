"""In-process :class:`JobQueuePort` adapter.

Runs handlers synchronously inline at ``enqueue`` time. Intended for
dev, tests, and single-process deployments where the operational cost
of running a separate worker is not justified. The production
settings validator refuses ``APP_JOBS_BACKEND=in_process`` so this
adapter never sees production traffic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from features.background_jobs.application.errors import UnknownJobError
from features.background_jobs.application.registry import JobHandlerRegistry

_logger = logging.getLogger("features.background_jobs.in_process")


@dataclass(slots=True)
class InProcessJobQueueAdapter:
    """Resolve the handler in the registry and call it inline."""

    registry: JobHandlerRegistry

    def enqueue(self, job_name: str, payload: dict[str, Any]) -> None:
        """Invoke the registered handler synchronously; raise on unknown jobs."""
        handler = self._resolve(job_name)
        _logger.info(
            "event=jobs.in_process.dispatch job=%s",
            job_name,
        )
        handler(payload)

    def enqueue_at(
        self,
        job_name: str,
        payload: dict[str, Any],
        run_at: datetime,
    ) -> None:
        """Refuse scheduling: the in-process adapter has no scheduler.

        Scheduled execution is a production concern; tests that need
        scheduled behaviour should wire the arq adapter against a
        fakeredis or testcontainer-backed Redis.
        """
        raise NotImplementedError(
            "InProcessJobQueueAdapter does not support enqueue_at; "
            "set APP_JOBS_BACKEND=arq for scheduled execution"
        )

    def _resolve(self, job_name: str) -> Any:
        if not self.registry.has(job_name):
            raise UnknownJobError(job_name=job_name)
        return self.registry.get(job_name)
