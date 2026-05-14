"""Adapter that renders the email and logs it at ``INFO`` instead of sending.

Intended for local development and tests. The settings validator refuses
to start with ``APP_EMAIL_BACKEND=console`` in production, so this
adapter never sees real traffic.

The adapter never logs the rendered body by default — password-reset
and email-verify templates render single-use tokens into the body, and
log read access SHOULD NOT be equivalent to "can complete a reset".
Operators correlate by ``body_sha256`` instead. Full-body logging is
gated behind ``APP_EMAIL_CONSOLE_LOG_BODIES=true`` AND
``APP_ENVIRONMENT=development``.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any

from app_platform.observability.redaction import redact_email
from app_platform.shared.result import Err, Ok, Result
from features.email.application.errors import (
    EmailError,
    TemplateRenderError,
    UnknownTemplateError,
)
from features.email.application.registry import EmailTemplateRegistry

_logger = logging.getLogger("features.email.console")


@dataclass(slots=True)
class ConsoleEmailAdapter:
    """Log the rendered email at ``INFO`` instead of dispatching it."""

    registry: EmailTemplateRegistry
    # When True AND ``environment == "development"``, the full body is
    # additionally logged at INFO. Default-off so reset/verify tokens
    # never appear in logs unless an operator explicitly opts in.
    log_bodies: bool = False
    environment: str = "development"

    def send(
        self,
        *,
        to: str,
        template_name: str,
        context: dict[str, Any],
    ) -> Result[None, EmailError]:
        try:
            message = self.registry.render(
                to=to, template_name=template_name, context=context
            )
        except UnknownTemplateError as exc:
            return Err(exc)
        except TemplateRenderError as exc:
            return Err(exc)

        body_bytes = message.body.encode("utf-8")
        body_sha256 = hashlib.sha256(body_bytes).hexdigest()
        _logger.info(
            "event=email.console.sent to=%s template=%s subject=%s "
            "body_len=%d body_sha256=%s",
            redact_email(message.to),
            template_name,
            message.subject,
            len(message.body),
            body_sha256,
        )
        # Full-body line is dev-only AND opt-in. Both conditions must
        # hold; the production settings validator refuses
        # ``APP_EMAIL_BACKEND=console`` so the ``environment`` guard is
        # defence-in-depth against future regressions.
        if self.log_bodies and self.environment == "development":
            _logger.info(
                "event=email.console.body to=%s template=%s body=%s",
                redact_email(message.to),
                template_name,
                message.body,
            )
        return Ok(None)
