"""Background-job registration for the email feature.

Defines the ``send_email`` handler the background-jobs feature dispatches.
The handler is intentionally a thin shim: it unpacks the payload and
calls the wired :class:`EmailPort` adapter, so the job queue does not
become a second copy of the email contract.

This module lives under ``composition`` because registering with the
job-handler registry is a composition-time concern, not application
logic. The handler itself does not import any other feature.
"""

from __future__ import annotations

import logging
from typing import Any

from app_platform.shared.result import Err
from features.background_jobs.application.registry import JobHandlerRegistry
from features.email.application.jobs import SEND_EMAIL_JOB
from features.email.application.ports.email_port import EmailPort

_logger = logging.getLogger("features.email.jobs")


def register_send_email_handler(
    registry: JobHandlerRegistry,
    email_port: EmailPort,
) -> None:
    """Register the ``send_email`` handler with the job-handler registry.

    The handler is registered once at composition time. The web process
    and the worker both call this so they agree on which job names are
    valid — registering only in the worker would let the web process
    enqueue ``send_email`` payloads that the queue would later reject.
    """

    def _handler(payload: dict[str, Any]) -> None:
        to = payload["to"]
        template_name = payload["template_name"]
        context = payload.get("context", {})
        result = email_port.send(
            to=to,
            template_name=template_name,
            context=context,
        )
        if isinstance(result, Err):
            # Surface the failure so arq treats the job as failed and
            # retries it according to its configured policy.
            _logger.error(
                "event=jobs.send_email.failed to=%s template=%s reason=%s",
                to,
                template_name,
                result.error,
            )
            raise RuntimeError(f"send_email failed: {result.error}")  # noqa: TRY004 — Result-type pattern match, not a type guard

    registry.register_handler(SEND_EMAIL_JOB, _handler)
