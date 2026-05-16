"""Unit tests for the runtime-agnostic worker scaffold's drain helpers.

``arq`` (and its ``on_shutdown`` hook) was removed in ROADMAP ETAPA I
step 5. ``src/worker.py`` is now a composition-root + handler/cron
registry scaffold with no job runtime; its reusable drain helpers
(engine dispose / Redis close / tracing flush) are kept callable so a
future runtime (AWS SQS + a Lambda worker) can re-bind them. These
tests pin that surface and assert ``worker.main()`` exits non-zero
with the "no runtime wired" message.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

import worker
from features.background_jobs.application.cron import CronSpec

pytestmark = pytest.mark.unit


def test_dispose_engine_disposes() -> None:
    """The reusable engine-dispose helper calls ``engine.dispose()``."""
    engine = MagicMock()
    worker.dispose_engine(engine)
    engine.dispose.assert_called_once_with()


def test_dispose_engine_swallows_failure() -> None:
    """A failing engine disposal is logged and swallowed."""
    engine = MagicMock()
    engine.dispose.side_effect = RuntimeError("pool already disposed")
    worker.dispose_engine(engine)  # must not raise
    engine.dispose.assert_called_once_with()


def test_dispose_engine_noop_when_none() -> None:
    """``None`` engine (nothing to dispose) is a clean no-op."""
    worker.dispose_engine(None)


def test_close_redis_closes_sync_client() -> None:
    """The reusable Redis-close helper calls ``redis.close()``."""
    redis_client = MagicMock()
    worker.close_redis(redis_client)
    redis_client.close.assert_called_once_with()


def test_close_redis_swallows_failure() -> None:
    """A failing Redis close is logged and swallowed."""
    redis_client = MagicMock()
    redis_client.close.side_effect = RuntimeError("connection reset")
    worker.close_redis(redis_client)  # must not raise
    redis_client.close.assert_called_once_with()


def test_close_redis_noop_when_none() -> None:
    """``None`` Redis client (the in-process backend owns none) is a no-op."""
    worker.close_redis(None)


def test_close_redis_awaits_coroutine_close() -> None:
    """When ``redis.close()`` is async, the helper drives it to completion."""
    closed = {"value": False}

    class _AsyncRedis:
        async def close(self) -> None:
            closed["value"] = True

    worker.close_redis(_AsyncRedis())
    assert closed["value"] is True


def test_drain_worker_runs_all_steps() -> None:
    """The full drain disposes the engine and closes Redis in order."""
    engine = MagicMock()
    redis_client = MagicMock()
    worker.drain_worker(engine=engine, redis_client=redis_client)
    engine.dispose.assert_called_once_with()
    redis_client.close.assert_called_once_with()


def test_drain_worker_continues_when_engine_dispose_raises() -> None:
    """A failing engine disposal does not skip the Redis close."""
    engine = MagicMock()
    engine.dispose.side_effect = RuntimeError("pool already disposed")
    redis_client = MagicMock()
    worker.drain_worker(engine=engine, redis_client=redis_client)
    engine.dispose.assert_called_once_with()
    redis_client.close.assert_called_once_with()


def test_no_arq_on_shutdown_symbol_remains() -> None:
    """The arq ``on_shutdown`` hook and its relay-tick globals are gone."""
    assert not hasattr(worker, "_on_shutdown")
    assert not hasattr(worker, "_wrap_relay_tick")
    assert not hasattr(worker, "_RELAY_TICK_IN_FLIGHT")
    assert "arq" not in worker.__dict__


def test_main_builds_scaffold_logs_and_exits_non_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``main()`` builds the scaffold, logs handlers + crons, exits non-zero.

    The scaffold build is the loud composition smoke test; we stub it
    so this unit test does not need a database, then assert the
    drain runs, the honest message is emitted, and the exit code is
    non-zero.
    """
    engine = MagicMock()
    scaffold = worker.WorkerScaffold(
        engine=engine,
        redis_client=None,
        jobs_settings=type("S", (), {"backend": "in_process"})(),
        registered_jobs=["send_email"],
        cron_specs=(
            CronSpec(
                name="outbox-relay",
                interval_seconds=5,
                run_at_startup=True,
                callable=lambda: None,
            ),
        ),
    )

    def _build() -> worker.WorkerScaffold:
        return scaffold

    monkeypatch.setattr(worker, "build_worker_scaffold", _build)

    exit_code = worker.main([])

    assert exit_code != 0
    # main() runs the drain so the scaffold's resources are released
    # before the honest non-zero exit.
    engine.dispose.assert_called_once_with()


def test_main_surfaces_composition_errors_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A composition failure propagates out of ``main()`` (loud, not silent)."""

    def _boom() -> object:
        raise RuntimeError("composition exploded")

    monkeypatch.setattr(worker, "build_worker_scaffold", _boom)

    with pytest.raises(RuntimeError, match="composition exploded"):
        worker.main([])


def test_no_runtime_message_states_the_roadmap_step() -> None:
    """The honest-refusal message names arq removal and the AWS step."""
    message = worker._NO_RUNTIME_MESSAGE
    assert "arq" in message
    assert "ROADMAP" in message
    assert "SQS" in message or "Lambda" in message


def test_scaffold_drain_delegates_to_drain_worker() -> None:
    """``WorkerScaffold.drain`` routes through the reusable drain helper."""
    engine = MagicMock()
    scaffold = worker.WorkerScaffold(
        engine=engine,
        redis_client=None,
        jobs_settings=type("S", (), {"backend": "in_process"})(),
    )
    scaffold.drain()
    engine.dispose.assert_called_once_with()


def test_close_redis_async_close_outside_running_loop() -> None:
    """``close_redis`` runs an async ``close()`` when no loop is running."""
    closed = {"value": False}

    class _AsyncRedis:
        async def close(self) -> None:
            await asyncio.sleep(0)
            closed["value"] = True

    worker.close_redis(_AsyncRedis())
    assert closed["value"] is True
