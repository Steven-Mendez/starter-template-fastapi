"""Unit tests for the email feature's ``send_email`` job handler registration.

These tests live under ``background_jobs/tests`` so the round-trip
(enqueue → handler → email port) can be exercised without dragging in
``email/tests`` infrastructure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.registry import JobHandlerRegistry
from features.email.adapters.outbound.console import ConsoleEmailAdapter
from features.email.application.jobs import SEND_EMAIL_JOB
from features.email.application.registry import EmailTemplateRegistry
from features.email.composition.jobs import register_send_email_handler
from features.email.tests.fakes.fake_email_port import FakeEmailPort

pytestmark = pytest.mark.unit


def test_register_then_enqueue_calls_email_port() -> None:
    jobs_registry = JobHandlerRegistry()
    email_port = FakeEmailPort(permissive=True)
    register_send_email_handler(jobs_registry, email_port)
    jobs_registry.seal()
    queue = InProcessJobQueueAdapter(registry=jobs_registry)

    queue.enqueue(
        SEND_EMAIL_JOB,
        {
            "to": "alice@example.com",
            "template_name": "auth/password_reset",
            "context": {"app_name": "Starter"},
        },
    )

    assert len(email_port.sent) == 1
    assert email_port.sent[0].to == "alice@example.com"
    assert email_port.sent[0].template_name == "auth/password_reset"
    assert email_port.sent[0].context == {"app_name": "Starter"}


def test_handler_raises_when_email_port_returns_err(tmp_path: Path) -> None:
    # Use the console adapter against an empty registry so the call
    # returns ``Err(UnknownTemplateError)`` — the handler then raises so
    # the job runtime treats the job as failed.
    email_registry = EmailTemplateRegistry()
    email_registry.seal()
    email_port = ConsoleEmailAdapter(registry=email_registry)

    jobs_registry = JobHandlerRegistry()
    register_send_email_handler(jobs_registry, email_port)
    queue = InProcessJobQueueAdapter(registry=jobs_registry)

    with pytest.raises(RuntimeError, match="send_email failed"):
        queue.enqueue(
            SEND_EMAIL_JOB,
            {"to": "a", "template_name": "missing", "context": {}},
        )


def test_handler_deduplicates_on_outbox_message_id() -> None:
    """Two deliveries with the same ``__outbox_message_id`` produce one send."""

    seen: set[str] = set()

    def _dedupe(message_id: str) -> bool:
        if message_id in seen:
            return False
        seen.add(message_id)
        return True

    jobs_registry = JobHandlerRegistry()
    email_port = FakeEmailPort(permissive=True)
    register_send_email_handler(jobs_registry, email_port, dedupe=_dedupe)
    jobs_registry.seal()
    queue = InProcessJobQueueAdapter(registry=jobs_registry)

    payload = {
        "to": "alice@example.com",
        "template_name": "auth/password_reset",
        "context": {"app_name": "Starter"},
        "__outbox_message_id": "11111111-1111-1111-1111-111111111111",
    }
    queue.enqueue(SEND_EMAIL_JOB, dict(payload))
    queue.enqueue(SEND_EMAIL_JOB, dict(payload))

    # Both invocations returned cleanly (no raise) but only one email
    # was actually sent — the second was a no-op via the dedup callable.
    assert len(email_port.sent) == 1


def test_handler_runs_when_no_outbox_message_id_present() -> None:
    """Non-outbox-fed payloads (no reserved key) still dispatch normally."""

    def _dedupe(_message_id: str) -> bool:  # pragma: no cover - never reached
        raise AssertionError("dedupe must not be consulted without the reserved key")

    jobs_registry = JobHandlerRegistry()
    email_port = FakeEmailPort(permissive=True)
    register_send_email_handler(jobs_registry, email_port, dedupe=_dedupe)
    jobs_registry.seal()
    queue = InProcessJobQueueAdapter(registry=jobs_registry)

    queue.enqueue(
        SEND_EMAIL_JOB,
        {
            "to": "bob@example.com",
            "template_name": "auth/email_verify",
            "context": {},
        },
    )
    assert len(email_port.sent) == 1


def test_re_enqueue_preserves_unknown_reserved_keys() -> None:
    """A redrive that re-enqueues a payload preserves every ``__*`` key.

    This is the forward-compat invariant: a future sibling change may
    add a reserved key (e.g. ``__trace``); legacy redrive tooling must
    carry it through verbatim so the new key reaches the new relay.
    """

    captured: list[dict[str, object]] = []

    def _capture_handler(payload: dict[str, object]) -> None:
        captured.append(dict(payload))

    jobs_registry = JobHandlerRegistry()
    jobs_registry.register_handler("redrive_capture", _capture_handler)
    jobs_registry.seal()
    queue = InProcessJobQueueAdapter(registry=jobs_registry)

    incoming = {
        "to": "alice@example.com",
        "template_name": "auth/password_reset",
        "context": {"app_name": "Starter"},
        "__outbox_message_id": "11111111-1111-1111-1111-111111111111",
        "__trace": {"traceparent": "00-abc"},
    }
    # Simulate redrive: the tooling receives the payload and re-enqueues
    # it. The handler under test must preserve every reserved key on
    # its way back through the queue.
    queue.enqueue("redrive_capture", dict(incoming))
    redriven = dict(captured[0])
    queue.enqueue("redrive_capture", redriven)

    assert captured[-1]["__trace"] == {"traceparent": "00-abc"}
    assert captured[-1]["__outbox_message_id"] == "11111111-1111-1111-1111-111111111111"
