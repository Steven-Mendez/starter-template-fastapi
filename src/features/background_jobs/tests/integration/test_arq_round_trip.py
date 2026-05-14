"""Unit-tier round-trip of the arq enqueue → worker → handler cycle.

The arq adapter writes jobs to Redis from synchronous code (the web
process), while the worker reads from the same Redis using the async
client. This test runs both halves against a single ``fakeredis``
backend to validate that the wire format produced by
:class:`ArqJobQueueAdapter` is consumable by arq's worker.

Previously marked ``integration`` even though it never touched a real
Redis — ``strengthen-test-contracts`` re-marks it as ``unit`` so the
marker reflects actual backend usage. The real-Redis round trip lives
in ``test_arq_redis_round_trip.py`` (testcontainers-backed,
``integration``-marked) and skips cleanly without Docker.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import fakeredis
import fakeredis.aioredis
import pytest
from arq import worker as arq_worker
from arq.worker import Worker

from features.background_jobs.adapters.outbound.arq import (
    ArqJobQueueAdapter,
    build_arq_functions,
)
from features.background_jobs.application.registry import JobHandlerRegistry

pytestmark = pytest.mark.unit


async def _noop_log_redis_info(_pool: Any, _logger: Callable[[str], None]) -> None:
    """Stand-in for ``arq.connections.log_redis_info`` — fakeredis lacks INFO."""


async def test_worker_processes_enqueued_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(arq_worker, "log_redis_info", _noop_log_redis_info)
    server = fakeredis.FakeServer()
    sync_client = fakeredis.FakeRedis(server=server)
    async_client = fakeredis.aioredis.FakeRedis(server=server)

    registry = JobHandlerRegistry()
    received: list[dict[str, object]] = []
    registry.register_handler("send_email", received.append)

    ArqJobQueueAdapter(registry=registry, redis_client=sync_client).enqueue(
        "send_email", {"to": "alice@example.com", "template_name": "x"}
    )

    worker = Worker(
        functions=build_arq_functions(registry),
        redis_pool=async_client,  # type: ignore[arg-type]
        burst=True,
        max_burst_jobs=1,
        handle_signals=False,
        poll_delay=0.05,
    )
    try:
        await worker.async_run()
    finally:
        await worker.close()
        await async_client.close()
        sync_client.close()

    assert received == [{"to": "alice@example.com", "template_name": "x"}]
