"""Tests for the lifespan finalizer's ``safe_finalize`` helper.

The lifespan finalizer wraps each shutdown step in
:func:`app_platform.api.lifespan.safe_finalize` so a single failing
step does not skip the remaining ones. Exercising the helper directly
keeps the test free of the full composition root while still asserting
the contract Wave 2's graceful-shutdown work promises.
"""

from __future__ import annotations

import logging

import pytest

from app_platform.api.lifespan import safe_finalize

pytestmark = pytest.mark.unit


def test_safe_finalize_runs_callable() -> None:
    calls: list[int] = []
    safe_finalize("step", lambda: calls.append(1))
    assert calls == [1]


def test_safe_finalize_swallows_exception(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _boom() -> None:
        raise RuntimeError("redis unreachable")

    with caplog.at_level(logging.WARNING, logger="app_platform.api.lifespan"):
        safe_finalize("redis", _boom)

    # The exception is swallowed (no re-raise) and surfaces as a warn log.
    record = next(
        (r for r in caplog.records if "lifespan.shutdown.step.failed" in r.message),
        None,
    )
    assert record is not None
    assert "redis" in record.message
    assert record.levelno == logging.WARNING


def test_safe_finalize_runs_subsequent_steps_after_failure() -> None:
    """Each step is independent — one failure does not break the next."""
    calls: list[str] = []

    def _failing() -> None:
        calls.append("failed")
        raise RuntimeError("nope")

    def _ok() -> None:
        calls.append("ok")

    safe_finalize("first", _failing)
    safe_finalize("second", _ok)
    assert calls == ["failed", "ok"]
