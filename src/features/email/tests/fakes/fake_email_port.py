"""In-memory :class:`EmailPort` for unit and e2e tests.

Records every send call so tests can assert which template went where
with what context, and returns :class:`Ok(None)` by default. Tests that
want to exercise the error path can set ``fail_with`` to an
:class:`EmailError`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.features.email.application.errors import EmailError
from src.platform.shared.result import Err, Ok, Result


@dataclass(frozen=True, slots=True)
class SentEmail:
    """One captured ``EmailPort.send`` call."""

    to: str
    template_name: str
    context: dict[str, Any]


@dataclass(slots=True)
class FakeEmailPort:
    """Recording fake of :class:`EmailPort` for tests."""

    sent: list[SentEmail] = field(default_factory=list)
    fail_with: EmailError | None = None

    def send(
        self,
        *,
        to: str,
        template_name: str,
        context: dict[str, Any],
    ) -> Result[None, EmailError]:
        self.sent.append(
            SentEmail(to=to, template_name=template_name, context=dict(context))
        )
        if self.fail_with is not None:
            return Err(self.fail_with)
        return Ok(None)

    def reset(self) -> None:
        self.sent.clear()
