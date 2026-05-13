"""Inbound port the rest of the application calls to send email.

The port is intentionally narrow: callers name a template (previously
registered with :class:`EmailTemplateRegistry`) and supply a context
dictionary. The active adapter renders the template via the registry
and dispatches the resulting message through its transport.
"""

from __future__ import annotations

from typing import Any, Protocol

from app_platform.shared.result import Result
from features.email.application.errors import EmailError


class EmailPort(Protocol):
    """Send a transactional email rendered from a registered template."""

    def send(
        self,
        *,
        to: str,
        template_name: str,
        context: dict[str, Any],
    ) -> Result[None, EmailError]:
        """Render ``template_name`` with ``context`` and deliver it to ``to``.

        Returns an :class:`Err` for any application-level failure
        (unknown template, render failure, transport failure). Adapters
        SHALL NOT raise for these cases.
        """
        ...
