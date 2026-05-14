"""SMTP adapter that delivers the rendered email via :mod:`smtplib`.

Supports the two common deployment shapes: implicit TLS on port 465
(``use_ssl=True``) and STARTTLS upgrade on submission port 587
(``use_starttls=True``). Authentication is optional — set it when the
provider requires it.

All smtplib exceptions are caught and surfaced as
:class:`DeliveryError` so callers always receive a ``Result`` and the
auth use cases do not need to know which library raised what.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any

from app_platform.observability.redaction import redact_email
from app_platform.shared.result import Err, Ok, Result
from features.email.application.errors import (
    DeliveryError,
    EmailError,
    TemplateRenderError,
    UnknownTemplateError,
)
from features.email.application.registry import EmailTemplateRegistry

_logger = logging.getLogger("features.email.smtp")


@dataclass(slots=True)
class SmtpEmailAdapter:
    """Send rendered emails over SMTP.

    The adapter is constructed once at startup and reused for the
    lifetime of the process. Each :meth:`send` opens a short-lived
    connection — long-lived connections are not worth the
    reconnect-on-error complexity in a starter.
    """

    registry: EmailTemplateRegistry
    host: str
    port: int
    from_address: str
    username: str | None = None
    password: str | None = None
    use_starttls: bool = True
    use_ssl: bool = False
    timeout: float = 10.0

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

        envelope = EmailMessage()
        envelope["From"] = self.from_address
        envelope["To"] = message.to
        envelope["Subject"] = message.subject
        envelope.set_content(message.body)

        try:
            self._dispatch(envelope)
        except (smtplib.SMTPException, OSError) as exc:
            _logger.exception(
                "event=email.smtp.failed to=%s template=%s",
                redact_email(to),
                template_name,
            )
            return Err(DeliveryError(reason=str(exc)))

        _logger.info(
            "event=email.smtp.sent to=%s template=%s",
            redact_email(to),
            template_name,
        )
        return Ok(None)

    def _dispatch(self, envelope: EmailMessage) -> None:
        ssl_context = ssl.create_default_context()
        if self.use_ssl:
            with smtplib.SMTP_SSL(
                self.host,
                self.port,
                timeout=self.timeout,
                context=ssl_context,
            ) as client:
                self._maybe_login(client)
                client.send_message(envelope)
            return

        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as client:
            if self.use_starttls:
                client.starttls(context=ssl_context)
                client.ehlo()
            self._maybe_login(client)
            client.send_message(envelope)

    def _maybe_login(self, client: smtplib.SMTP) -> None:
        if self.username and self.password:
            client.login(self.username, self.password)
