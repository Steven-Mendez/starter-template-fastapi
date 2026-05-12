"""Unit tests for :class:`ArqJobQueueAdapter` using ``fakeredis``.

Asserts the adapter writes the same Redis keys arq's worker expects so
swapping a real Redis instance does not change behaviour.
"""

from __future__ import annotations

import pickle
from datetime import datetime, timedelta, timezone

import fakeredis
import pytest
from arq import constants as arq_constants

from src.features.background_jobs.adapters.outbound.arq import ArqJobQueueAdapter
from src.features.background_jobs.application.errors import UnknownJobError
from src.features.background_jobs.application.registry import JobHandlerRegistry

pytestmark = pytest.mark.unit


@pytest.fixture
def registry() -> JobHandlerRegistry:
    r = JobHandlerRegistry()
    r.register_handler("send_email", lambda payload: None)
    return r


@pytest.fixture
def redis_client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis()


def test_enqueue_pushes_to_arq_queue(
    registry: JobHandlerRegistry, redis_client: fakeredis.FakeRedis
) -> None:
    adapter = ArqJobQueueAdapter(registry=registry, redis_client=redis_client)

    adapter.enqueue("send_email", {"to": "alice@example.com"})

    queued: list[bytes] = redis_client.zrange(  # type: ignore[assignment]
        arq_constants.default_queue_name, 0, -1
    )
    assert len(queued) == 1
    job_id = queued[0].decode()
    raw: bytes | None = redis_client.get(  # type: ignore[assignment]
        f"{arq_constants.job_key_prefix}{job_id}"
    )
    assert raw is not None
    job = pickle.loads(raw)
    # arq's serialize_job stores: t (try), f (function name), a (args),
    # k (kwargs), et (enqueue_time_ms). We pass the payload as a single
    # positional arg so the worker sees ``handler(ctx, payload)``.
    assert job["f"] == "send_email"
    assert job["a"] == ({"to": "alice@example.com"},)
    assert job["k"] == {}


def test_enqueue_unknown_job_raises(redis_client: fakeredis.FakeRedis) -> None:
    registry = JobHandlerRegistry()
    adapter = ArqJobQueueAdapter(registry=registry, redis_client=redis_client)

    with pytest.raises(UnknownJobError):
        adapter.enqueue("nope", {})


def test_enqueue_at_uses_deferred_score(
    registry: JobHandlerRegistry, redis_client: fakeredis.FakeRedis
) -> None:
    adapter = ArqJobQueueAdapter(registry=registry, redis_client=redis_client)
    run_at = datetime.now(timezone.utc) + timedelta(hours=1)

    adapter.enqueue_at("send_email", {"to": "a@e.com"}, run_at)

    score_pairs: list[tuple[bytes, float]] = redis_client.zrange(  # type: ignore[assignment]
        arq_constants.default_queue_name, 0, -1, withscores=True
    )
    assert len(score_pairs) == 1
    _, score = score_pairs[0]
    expected_ms = int(run_at.timestamp() * 1000)
    # Allow small drift from internal time() resolution.
    assert abs(int(score) - expected_ms) < 1000


def test_enqueue_at_requires_tz_aware(
    registry: JobHandlerRegistry, redis_client: fakeredis.FakeRedis
) -> None:
    adapter = ArqJobQueueAdapter(registry=registry, redis_client=redis_client)
    with pytest.raises(ValueError, match="timezone-aware"):
        adapter.enqueue_at("send_email", {}, datetime(2026, 1, 1))


def test_custom_queue_name(
    registry: JobHandlerRegistry, redis_client: fakeredis.FakeRedis
) -> None:
    adapter = ArqJobQueueAdapter(
        registry=registry, redis_client=redis_client, queue_name="custom:queue"
    )
    adapter.enqueue("send_email", {})
    assert redis_client.zcard("custom:queue") == 1
    assert redis_client.zcard(arq_constants.default_queue_name) == 0
