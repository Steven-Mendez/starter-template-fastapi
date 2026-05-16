"""Background-job registration for the email feature.

Defines the ``send_email`` handler the background-jobs feature dispatches.
The handler is intentionally a thin shim: it unpacks the payload and
calls the wired :class:`EmailPort` adapter, so the job queue does not
become a second copy of the email contract.

This module lives under ``composition`` because registering with the
job-handler registry is a composition-time concern, not application
logic. The handler itself does not import any other feature.

When the handler is invoked through the outbox relay, the payload
carries the reserved key ``__outbox_message_id``. The handler is
at-least-once on the relay side, so a second delivery with the same
id MUST be a no-op. Wiring code passes a ``dedupe`` callable that
records the message id (typically an ``INSERT`` into the outbox
feature's ``processed_outbox_messages`` table) and returns ``False``
if the id was already recorded — in that case the handler skips the
side effect and returns success. When no ``dedupe`` callable is wired
(e.g. legacy producers that do not feed through the outbox), the
handler runs unconditionally.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app_platform.observability.redaction import redact_email
from app_platform.shared.result import Err
from features.background_jobs.application.registry import JobHandlerRegistry
from features.email.application.jobs import SEND_EMAIL_JOB
from features.email.application.ports.email_port import EmailPort

_logger = logging.getLogger("features.email.jobs")

# Reserved payload key the outbox relay injects. Mirrored here so the
# email handler does not need to import the outbox feature (forbidden
# by the import-linter contract). The string itself is the cross-
# feature contract; see ``docs/outbox.md``.
_OUTBOX_MESSAGE_ID_KEY = "__outbox_message_id"

# Returns ``True`` if the message id was newly recorded (the handler
# should proceed to send), ``False`` if it was already processed (the
# handler MUST short-circuit to ``Ok`` / no-op).
HandlerDedupe = Callable[[str], bool]


def register_send_email_handler(
    registry: JobHandlerRegistry,
    email_port: EmailPort,
    *,
    dedupe: HandlerDedupe | None = None,
) -> None:
    """Register the ``send_email`` handler with the job-handler registry.

    The handler is registered once at composition time. The web process
    and the worker both call this so they agree on which job names are
    valid — registering only in the worker would let the web process
    enqueue ``send_email`` payloads that the queue would later reject.

    ``dedupe``, when provided, is invoked with the value of
    ``__outbox_message_id`` from the incoming payload (if present). A
    ``False`` return short-circuits the handler to a no-op so the
    relay's at-least-once redelivery never produces a duplicate email.
    """

    def _handler(payload: dict[str, Any]) -> None:
        message_id = payload.get(_OUTBOX_MESSAGE_ID_KEY)
        if (
            dedupe is not None
            and isinstance(message_id, str)
            and not dedupe(message_id)
        ):
            # ``to`` is logged only in redacted form: this line predates
            # the PII filter's coverage of positional %s args, so the
            # call site is responsible for masking the local part.
            _logger.info(
                "event=jobs.send_email.deduped outbox_message_id=%s to=%s",
                message_id,
                redact_email(payload.get("to", "")),
            )
            return
        to = payload["to"]
        template_name = payload["template_name"]
        context = payload.get("context", {})
        result = email_port.send(
            to=to,
            template_name=template_name,
            context=context,
        )
        if isinstance(result, Err):
            # Surface the failure so the job runtime treats the job as
            # failed and retries it per its policy (the outbox relay's
            # at-least-once redelivery in the current shipped path). ``to`` is
            # passed through ``redact_email`` because positional %s args
            # bypass the stdlib PII filter (it intentionally scans only
            # record attributes, not string args).
            _logger.error(
                "event=jobs.send_email.failed to=%s template=%s reason=%s",
                redact_email(to),
                template_name,
                result.error,
            )
            raise RuntimeError(f"send_email failed: {result.error}")  # noqa: TRY004 — Result-type pattern match, not a type guard

    registry.register_handler(SEND_EMAIL_JOB, _handler)
