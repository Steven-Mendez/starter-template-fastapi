"""arq-backed :class:`JobQueuePort` adapter.

The web process needs to enqueue jobs from inside synchronous use cases
without entering an async context. arq's own :class:`ArqRedis` is
async-only, so this adapter writes directly to the same Redis keys arq
expects, using the synchronous ``redis-py`` client and arq's
:func:`serialize_job` helper to stay wire-compatible.

Worker-side execution is unchanged: the worker entrypoint
(``src/worker.py``) consumes the queue using arq's standard
:func:`run_worker` and the handlers wrapped by
:func:`build_arq_functions`.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import redis as redis_lib
from arq import constants as arq_constants
from arq.jobs import serialize_job

from app_platform.observability.metrics import JOBS_ENQUEUED_TOTAL
from features.background_jobs.application.errors import UnknownJobError
from features.background_jobs.application.registry import JobHandlerRegistry

_logger = logging.getLogger("features.background_jobs.arq")

# Match arq's default 24h job-record TTL so the keys disappear on
# their own if the worker is offline and the job is never picked up.
_DEFAULT_EXPIRES_MS: int = arq_constants.expires_extra_ms


@dataclass(slots=True)
class ArqJobQueueAdapter:
    """Push jobs onto an arq-compatible Redis queue from sync code.

    The adapter does not own its Redis client — callers pass one in
    (typically the same client used by the rate limiter and principal
    cache) so connection management stays in one place.

    The ``registry`` reference is held solely to validate that
    ``job_name`` is registered before the payload is enqueued.
    """

    registry: JobHandlerRegistry
    redis_client: redis_lib.Redis
    queue_name: str = arq_constants.default_queue_name
    expires_ms: int = _DEFAULT_EXPIRES_MS

    def enqueue(self, job_name: str, payload: dict[str, Any]) -> None:
        """Enqueue ``job_name`` for immediate execution."""
        if not self.registry.has(job_name):
            raise UnknownJobError(job_name=job_name)
        enqueue_time_ms = int(time.time() * 1000)
        self._push(
            job_name=job_name,
            payload=payload,
            enqueue_time_ms=enqueue_time_ms,
            score=enqueue_time_ms,
        )
        JOBS_ENQUEUED_TOTAL.add(1, attributes={"handler": job_name})
        _logger.info(
            "event=jobs.arq.enqueued job=%s queue=%s",
            job_name,
            self.queue_name,
        )

    def enqueue_at(
        self,
        job_name: str,
        payload: dict[str, Any],
        run_at: datetime,
    ) -> None:
        """Enqueue ``job_name`` to be picked up at ``run_at`` (UTC)."""
        if not self.registry.has(job_name):
            raise UnknownJobError(job_name=job_name)
        if run_at.tzinfo is None:
            raise ValueError("run_at must be timezone-aware")
        enqueue_time_ms = int(time.time() * 1000)
        score = int(run_at.astimezone(UTC).timestamp() * 1000)
        self._push(
            job_name=job_name,
            payload=payload,
            enqueue_time_ms=enqueue_time_ms,
            score=score,
        )
        _logger.info(
            "event=jobs.arq.scheduled job=%s queue=%s run_at=%s",
            job_name,
            self.queue_name,
            run_at.isoformat(),
        )

    def _push(
        self,
        *,
        job_name: str,
        payload: dict[str, Any],
        enqueue_time_ms: int,
        score: int,
    ) -> None:
        job_id = uuid.uuid4().hex
        job_key = f"{arq_constants.job_key_prefix}{job_id}"
        # arq calls handlers as ``handler(ctx, *args, **kwargs)`` — passing
        # ``payload`` as a single positional arg keeps the registry's
        # ``Callable[[dict[str, Any]], None]`` signature intact.
        data = serialize_job(job_name, (payload,), {}, None, enqueue_time_ms)
        pipe = self.redis_client.pipeline()
        pipe.psetex(job_key, self.expires_ms, data)
        pipe.zadd(self.queue_name, {job_id: score})
        pipe.execute()
