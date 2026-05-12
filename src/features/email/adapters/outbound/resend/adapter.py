"""Resend HTTP adapter for :class:`EmailPort`.

POSTs the rendered email to Resend's `/emails` endpoint using a
long-lived :class:`httpx.Client`. The adapter is sync — like
:class:`SmtpEmailAdapter` — and is reused across requests; ``httpx.Client``
is threadsafe for FastAPI's threadpool dispatch.

Retry policy is intentionally absent. Callers that want at-least-once
delivery enqueue the ``send_email`` background job; retrying at the
adapter layer would risk double-sends on a non-idempotent provider API.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

from src.features.email.application.errors import (
    DeliveryError,
    EmailError,
    TemplateRenderError,
    UnknownTemplateError,
)
from src.features.email.application.registry import EmailTemplateRegistry
from src.platform.shared.result import Err, Ok, Result

_logger = logging.getLogger("src.features.email.resend")

_DEFAULT_BASE_URL = "https://api.resend.com"
_SEND_PATH = "/emails"


@dataclass(slots=True)
class ResendEmailAdapter:
    """Send rendered emails via Resend's HTTP API.

    The :class:`httpx.Client` is built in ``__post_init__`` from the
    configured ``base_url`` / ``timeout`` and held for the process
    lifetime. Tests inject a pre-built client (with a respx-mocked
    transport) by passing ``client=...`` explicitly.
    """

    registry: EmailTemplateRegistry
    api_key: str
    from_address: str
    base_url: str = _DEFAULT_BASE_URL
    timeout: float = 10.0
    client: httpx.Client = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )

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

        payload = {
            "from": self.from_address,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body,
        }

        try:
            response = self.client.post(_SEND_PATH, json=payload)
        except httpx.HTTPError as exc:
            _logger.error(
                "event=email.resend.failed to=%s template=%s reason=%s",
                to,
                template_name,
                exc,
            )
            return Err(DeliveryError(reason=str(exc)))

        if 200 <= response.status_code < 300:
            _logger.info(
                "event=email.resend.sent to=%s template=%s",
                to,
                template_name,
            )
            return Ok(None)

        reason = _format_failure(response)
        _logger.error(
            "event=email.resend.failed to=%s template=%s status=%s reason=%s",
            to,
            template_name,
            response.status_code,
            reason,
        )
        return Err(DeliveryError(reason=reason))


def _format_failure(response: httpx.Response) -> str:
    status = response.status_code
    detail: str | None = None
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict):
        # Resend wraps the failure reason in either "message" or "error"
        # depending on the failure mode. Fall through to the raw body
        # text when neither is present.
        candidate = body.get("message") or body.get("error")
        if isinstance(candidate, str):
            detail = candidate
    if detail is None:
        detail = response.text.strip() or "(no body)"

    if status >= 500:
        return f"resend transient error: {status} {detail}"
    return f"resend rejected: {status} {detail}"
