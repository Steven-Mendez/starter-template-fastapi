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
from features.email.application.registry import EmailTemplateRegistry
from features.email.composition.jobs import (
    SEND_EMAIL_JOB,
    register_send_email_handler,
)
from features.email.tests.fakes.fake_email_port import FakeEmailPort

pytestmark = pytest.mark.unit


def test_register_then_enqueue_calls_email_port() -> None:
    jobs_registry = JobHandlerRegistry()
    email_port = FakeEmailPort()
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
    # arq treats the job as failed.
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
