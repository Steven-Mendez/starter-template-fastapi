"""Adapter that renders the email and logs it at ``INFO`` instead of sending.

Intended for local development and tests. The settings validator refuses
to start with ``APP_EMAIL_BACKEND=console`` in production, so this
adapter never sees real traffic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.features.email.application.errors import (
    EmailError,
    TemplateRenderError,
    UnknownTemplateError,
)
from src.features.email.application.registry import EmailTemplateRegistry
from src.platform.shared.result import Err, Ok, Result

_logger = logging.getLogger("src.features.email.console")


@dataclass(slots=True)
class ConsoleEmailAdapter:
    """Log the rendered email at ``INFO`` instead of dispatching it."""

    registry: EmailTemplateRegistry

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

        _logger.info(
            "event=email.console.sent to=%s template=%s subject=%s body=%s",
            message.to,
            template_name,
            message.subject,
            message.body,
        )
        return Ok(None)
