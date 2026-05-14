"""Unit tests for the arq worker's ``on_shutdown`` hook.

The worker's ``on_shutdown`` is the only place where the SQLAlchemy
engine and Redis client built during composition get disposed/closed
in the worker process. These tests target the public surface of that
hook without spinning up an actual arq worker — we drive the module-
level handles directly and assert each finalizer step runs (or is
skipped cleanly when a step raises).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

import worker

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_worker_module_state() -> Any:
    """Clear the module-level shutdown handles between tests.

    ``worker._on_shutdown`` reads module-level globals populated by
    composition. Each test sets only what it needs; this fixture
    restores defaults so cross-test bleed cannot mask a regression.
    """
    yield
    worker._RELAY_TICK_IN_FLIGHT = None
    worker._RELAY_TICK_IDLE = None
    worker._ENGINE = None
    worker._REDIS_CLIENT = None
    worker._SHUTDOWN_TIMEOUT_SECONDS = 30.0


def test_wrap_relay_tick_sets_and_clears_event() -> None:
    """The wrapper flips the in-flight flag during the tick body."""
    observed: list[bool] = []

    async def _tick(_ctx: dict[str, Any]) -> None:
        # ``observed`` snapshots the flag while the tick is executing.
        assert worker._RELAY_TICK_IN_FLIGHT is not None
        observed.append(worker._RELAY_TICK_IN_FLIGHT.is_set())

    wrapped = worker._wrap_relay_tick(_tick)
    asyncio.run(wrapped({}))

    assert observed == [True]
    assert worker._RELAY_TICK_IN_FLIGHT is not None
    assert worker._RELAY_TICK_IN_FLIGHT.is_set() is False


def test_wrap_relay_tick_clears_event_on_exception() -> None:
    """The wrapper clears the flag even when the inner tick raises."""

    async def _failing_tick(_ctx: dict[str, Any]) -> None:
        raise RuntimeError("boom")

    wrapped = worker._wrap_relay_tick(_failing_tick)
    with pytest.raises(RuntimeError, match="boom"):
        asyncio.run(wrapped({}))

    assert worker._RELAY_TICK_IN_FLIGHT is not None
    assert worker._RELAY_TICK_IN_FLIGHT.is_set() is False


def test_on_shutdown_disposes_engine_and_closes_redis() -> None:
    """Both teardown calls fire on the happy path."""
    engine = MagicMock()
    redis_client = MagicMock()
    worker._set_shutdown_handles(
        engine=engine,
        redis_client=redis_client,
        shutdown_timeout_seconds=1.0,
    )

    asyncio.run(worker._on_shutdown({}))

    engine.dispose.assert_called_once_with()
    redis_client.close.assert_called_once_with()


def test_on_shutdown_continues_when_engine_dispose_raises() -> None:
    """A failing engine disposal does not skip Redis close."""
    engine = MagicMock()
    engine.dispose.side_effect = RuntimeError("pool already disposed")
    redis_client = MagicMock()
    worker._set_shutdown_handles(
        engine=engine,
        redis_client=redis_client,
        shutdown_timeout_seconds=1.0,
    )

    asyncio.run(worker._on_shutdown({}))

    engine.dispose.assert_called_once_with()
    redis_client.close.assert_called_once_with()


def test_on_shutdown_waits_for_in_flight_relay_tick() -> None:
    """``on_shutdown`` blocks until the relay tick clears the flag."""
    engine = MagicMock()
    redis_client = MagicMock()
    worker._set_shutdown_handles(
        engine=engine,
        redis_client=redis_client,
        shutdown_timeout_seconds=2.0,
    )

    async def _scenario() -> None:
        # Simulate an in-flight tick: in_flight set, idle cleared.
        in_flight, idle = worker._ensure_relay_events()
        in_flight.set()
        idle.clear()

        shutdown_task = asyncio.create_task(worker._on_shutdown({}))
        # Yield so the shutdown task starts and is parked on ``idle.wait()``.
        await asyncio.sleep(0)
        assert engine.dispose.called is False
        # Simulate the relay tick finishing: idle is set, in_flight clears.
        in_flight.clear()
        idle.set()
        await shutdown_task

    asyncio.run(_scenario())

    engine.dispose.assert_called_once_with()
    redis_client.close.assert_called_once_with()


def test_on_shutdown_bounds_drain_by_timeout() -> None:
    """A relay tick that never finishes does not hang the worker."""
    engine = MagicMock()
    redis_client = MagicMock()
    worker._set_shutdown_handles(
        engine=engine,
        redis_client=redis_client,
        shutdown_timeout_seconds=0.2,
    )

    async def _scenario() -> None:
        in_flight, idle = worker._ensure_relay_events()
        in_flight.set()
        idle.clear()
        await worker._on_shutdown({})

    asyncio.run(_scenario())

    # Engine and Redis still get disposed after the drain timeout.
    engine.dispose.assert_called_once_with()
    redis_client.close.assert_called_once_with()


def test_on_shutdown_awaits_coroutine_redis_close() -> None:
    """When ``redis.close()`` is async, ``on_shutdown`` awaits it."""
    engine = MagicMock()
    closed = {"value": False}

    class _AsyncRedis:
        async def close(self) -> None:
            closed["value"] = True

    redis_client = _AsyncRedis()
    worker._set_shutdown_handles(
        engine=engine,
        redis_client=redis_client,
        shutdown_timeout_seconds=1.0,
    )

    asyncio.run(worker._on_shutdown({}))

    assert closed["value"] is True
    engine.dispose.assert_called_once_with()
