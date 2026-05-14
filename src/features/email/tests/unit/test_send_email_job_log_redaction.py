"""Regression: the ``send_email`` job handler must redact ``to`` in logs.

The ``jobs.send_email.failed`` log line interpolates the recipient as a
positional ``%s`` arg. The stdlib ``PiiLogFilter`` intentionally does
not scan plain-string positional args (see
``test_pii_filter.test_filter_does_not_scan_plain_string_args``), so
the call site MUST mask the email itself with
:func:`app_platform.observability.redaction.redact_email`.

This file pins that contract so a future edit cannot silently drop
the mask and reintroduce a PII leak.
"""

from __future__ import annotations

import logging

import pytest

from features.background_jobs.adapters.outbound.in_process import (
    InProcessJobQueueAdapter,
)
from features.background_jobs.application.registry import JobHandlerRegistry
from features.email.application.errors import DeliveryError
from features.email.application.jobs import SEND_EMAIL_JOB
from features.email.composition.jobs import register_send_email_handler
from features.email.tests.fakes.fake_email_port import FakeEmailPort

pytestmark = pytest.mark.unit


def test_failure_log_does_not_leak_raw_email(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """When the port returns ``Err``, the failure log must mask ``to``.

    The handler raises after logging — the assertion runs inside the
    ``pytest.raises`` block so we catch the log line emitted on the
    failing path.
    """
    jobs_registry = JobHandlerRegistry()
    email_port = FakeEmailPort(
        permissive=True, fail_with=DeliveryError(reason="smtp 550")
    )
    register_send_email_handler(jobs_registry, email_port)
    jobs_registry.seal()
    queue = InProcessJobQueueAdapter(registry=jobs_registry)

    with (
        caplog.at_level(logging.ERROR, logger="features.email.jobs"),
        pytest.raises(RuntimeError, match="send_email failed"),
    ):
        queue.enqueue(
            SEND_EMAIL_JOB,
            {
                "to": "alice@example.com",
                "template_name": "auth/password_reset",
                "context": {},
            },
        )

    # The raw local part must not appear anywhere in the captured text;
    # the redacted form must.
    assert "alice@example.com" not in caplog.text
    assert "a***@example.com" in caplog.text
    # Sanity: the event tag we asserted on is the one we expect.
    assert "event=jobs.send_email.failed" in caplog.text


def test_dedupe_log_does_not_leak_raw_email(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The dedup short-circuit log line must also mask ``to``.

    A redelivery hitting the dedup table is the common path under the
    outbox relay's at-least-once semantics, so this code runs in
    production whenever an email is replayed.
    """
    jobs_registry = JobHandlerRegistry()
    email_port = FakeEmailPort(permissive=True)

    # A dedupe callable that always reports "already processed" so the
    # handler hits the deduped log line on every invocation.
    def _always_seen(_message_id: str) -> bool:
        return False

    register_send_email_handler(jobs_registry, email_port, dedupe=_always_seen)
    jobs_registry.seal()
    queue = InProcessJobQueueAdapter(registry=jobs_registry)

    with caplog.at_level(logging.INFO, logger="features.email.jobs"):
        queue.enqueue(
            SEND_EMAIL_JOB,
            {
                "to": "alice@example.com",
                "template_name": "auth/password_reset",
                "context": {},
                "__outbox_message_id": "11111111-1111-1111-1111-111111111111",
            },
        )

    # The handler short-circuited (no send) and emitted the deduped log.
    assert email_port.sent == []
    assert "alice@example.com" not in caplog.text
    assert "a***@example.com" in caplog.text
    assert "event=jobs.send_email.deduped" in caplog.text
