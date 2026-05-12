"""Unit tests for :class:`JobHandlerRegistry`."""

from __future__ import annotations

import pytest

from src.features.background_jobs.application.errors import (
    HandlerAlreadyRegisteredError,
    UnknownJobError,
)
from src.features.background_jobs.application.registry import JobHandlerRegistry

pytestmark = pytest.mark.unit


def test_register_and_get_returns_handler() -> None:
    registry = JobHandlerRegistry()
    calls: list[dict[str, object]] = []

    def handler(payload: dict[str, object]) -> None:
        calls.append(payload)

    registry.register_handler("send_email", handler)

    assert registry.has("send_email")
    assert registry.registered_jobs() == {"send_email"}
    registry.get("send_email")({"to": "a"})
    assert calls == [{"to": "a"}]


def test_get_unknown_job_raises() -> None:
    registry = JobHandlerRegistry()
    with pytest.raises(UnknownJobError):
        registry.get("nope")


def test_duplicate_registration_raises() -> None:
    registry = JobHandlerRegistry()

    def handler(payload: dict[str, object]) -> None:
        pass

    registry.register_handler("send_email", handler)
    with pytest.raises(HandlerAlreadyRegisteredError):
        registry.register_handler("send_email", handler)


def test_seal_blocks_further_registrations() -> None:
    registry = JobHandlerRegistry()
    registry.seal()
    assert registry.sealed
    with pytest.raises(RuntimeError, match="sealed"):
        registry.register_handler("x", lambda payload: None)
