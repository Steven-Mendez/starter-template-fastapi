"""Integration round-trip of the arq adapter against a real Redis.

The fakeredis-backed companion test
(``test_arq_round_trip.py``) covers wire-format compatibility without
Docker. This test spins up an ephemeral ``redis:7`` testcontainer so
the same round trip is exercised against actual Redis semantics —
catching ``EVAL`` / ``ZADD`` / TTL behaviours fakeredis cannot model.

Skipped cleanly when Docker is unavailable or when
``KANBAN_SKIP_TESTCONTAINERS=1`` is set (the canonical opt-out
documented in ``CLAUDE.md``).
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from typing import Any

import pytest
import redis as redis_lib
from arq import worker as arq_worker
from arq.worker import Worker

from features.background_jobs.adapters.outbound.arq import (
    ArqJobQueueAdapter,
    build_arq_functions,
)
from features.background_jobs.application.registry import JobHandlerRegistry

pytestmark = pytest.mark.integration


def _docker_available() -> bool:
    if os.environ.get("KANBAN_SKIP_TESTCONTAINERS") == "1":
        return False
    try:
        from testcontainers.redis import (  # type: ignore[import-untyped]  # noqa: F401
            RedisContainer,
        )
    except Exception:
        return False
    try:
        import docker  # type: ignore[import-untyped]

        docker.from_env().ping()
    except Exception:
        return False
    return True


@pytest.fixture(scope="module")
def redis_container() -> Iterator[Any]:
    if not _docker_available():
        pytest.skip("Docker / testcontainers Redis not available")
    from testcontainers.redis import (
        RedisContainer,
    )

    with RedisContainer("redis:7") as container:
        yield container


async def _noop_log_redis_info(_pool: Any, _logger: Callable[[str], None]) -> None:
    """No-op replacement for arq's startup INFO log.

    arq's own ``log_redis_info`` issues a ``INFO`` command which works
    fine against a real Redis, but the worker also calls it with a
    detailed logger expectation; replacing with a no-op keeps the
    test focused on the round-trip rather than on the startup log
    plumbing (which the existing fakeredis test also stubs out).
    """


async def test_worker_processes_enqueued_job_against_real_redis(
    redis_container: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(arq_worker, "log_redis_info", _noop_log_redis_info)

    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    redis_url = f"redis://{host}:{port}/0"

    sync_client = redis_lib.Redis.from_url(redis_url, decode_responses=False)
    sync_client.flushdb()

    registry = JobHandlerRegistry()
    received: list[dict[str, object]] = []
    registry.register_handler("send_email", received.append)

    ArqJobQueueAdapter(registry=registry, redis_client=sync_client).enqueue(
        "send_email", {"to": "alice@example.com", "template_name": "x"}
    )

    # Use arq's stock async pool against the same Redis URL so the
    # worker reads what the sync adapter wrote.
    from arq.connections import RedisSettings, create_pool

    pool = await create_pool(RedisSettings.from_dsn(redis_url))
    worker = Worker(
        functions=build_arq_functions(registry),
        redis_pool=pool,
        burst=True,
        max_burst_jobs=1,
        handle_signals=False,
        poll_delay=0.05,
    )
    try:
        await worker.async_run()
    finally:
        await worker.close()
        await pool.aclose()
        sync_client.close()

    assert received == [{"to": "alice@example.com", "template_name": "x"}]
