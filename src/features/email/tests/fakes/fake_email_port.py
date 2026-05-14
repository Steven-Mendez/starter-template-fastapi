"""In-memory :class:`EmailPort` for unit and e2e tests.

Records every send call so tests can assert which template went where
with what context, and returns :class:`Ok(None)` by default. Tests that
want to exercise the error path can set ``fail_with`` to an
:class:`EmailError`.

The fake mirrors the real adapters' template-registry validation. A
caller MUST either pass an :class:`EmailTemplateRegistry` (strict — the
fake returns ``Err(UnknownTemplateError)`` for unregistered names) or
opt into permissive mode with ``permissive=True`` (the fake accepts any
template name). Defaulting to strict prevents auth e2e tests from
silently masking a missing template registration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app_platform.shared.result import Err, Ok, Result
from features.email.application.errors import EmailError, UnknownTemplateError
from features.email.application.registry import EmailTemplateRegistry


@dataclass(frozen=True, slots=True)
class SentEmail:
    """One captured ``EmailPort.send`` call."""

    to: str
    template_name: str
    context: dict[str, Any]


@dataclass(slots=True)
class FakeEmailPort:
    """Recording fake of :class:`EmailPort` for tests.

    Pass ``registry`` to mirror the real adapters' template lookup, or
    ``permissive=True`` to accept any template name (the legacy
    behaviour — kept for unit tests that exercise the handler / logging
    paths without caring about template validity).
    """

    registry: EmailTemplateRegistry | None = None
    permissive: bool = False
    sent: list[SentEmail] = field(default_factory=list)
    fail_with: EmailError | None = None

    def __post_init__(self) -> None:
        if self.registry is None and not self.permissive:
            raise ValueError(
                "FakeEmailPort requires either a registry or permissive=True; "
                "the strict default mirrors the real adapters so missing "
                "template registrations cannot hide in tests."
            )

    def send(
        self,
        *,
        to: str,
        template_name: str,
        context: dict[str, Any],
    ) -> Result[None, EmailError]:
        if self.registry is not None and not self.registry.has(template_name):
            return Err(UnknownTemplateError(template_name=template_name))
        self.sent.append(
            SentEmail(to=to, template_name=template_name, context=dict(context))
        )
        if self.fail_with is not None:
            return Err(self.fail_with)
        return Ok(None)

    def reset(self) -> None:
        self.sent.clear()
