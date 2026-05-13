"""Unit tests for :class:`InProcessJobQueueAdapter`."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.errors import UnknownJobError
from features.background_jobs.application.registry import JobHandlerRegistry

pytestmark = pytest.mark.unit


def test_enqueue_runs_handler_inline() -> None:
    registry = JobHandlerRegistry()
    calls: list[dict[str, object]] = []

    registry.register_handler("send_email", calls.append)
    adapter = InProcessJobQueueAdapter(registry=registry)

    adapter.enqueue("send_email", {"to": "a@example.com"})

    assert calls == [{"to": "a@example.com"}]


def test_enqueue_unknown_job_raises() -> None:
    registry = JobHandlerRegistry()
    adapter = InProcessJobQueueAdapter(registry=registry)

    with pytest.raises(UnknownJobError):
        adapter.enqueue("never-registered", {})


def test_handler_exception_propagates() -> None:
    registry = JobHandlerRegistry()

    def boom(payload: dict[str, object]) -> None:
        raise ValueError("boom")

    registry.register_handler("boom", boom)
    adapter = InProcessJobQueueAdapter(registry=registry)

    with pytest.raises(ValueError, match="boom"):
        adapter.enqueue("boom", {})


def test_enqueue_at_unsupported() -> None:
    registry = JobHandlerRegistry()
    registry.register_handler("noop", lambda payload: None)
    adapter = InProcessJobQueueAdapter(registry=registry)

    with pytest.raises(NotImplementedError):
        adapter.enqueue_at("noop", {}, datetime.now(UTC))
