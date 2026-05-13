"""Application-layer errors for the email feature."""

from __future__ import annotations

from dataclasses import dataclass

from app_platform.shared.errors import ApplicationError


class EmailError(ApplicationError):
    """Base class for email-feature errors returned as ``Err`` values."""


@dataclass(frozen=True, slots=True)
class UnknownTemplateError(EmailError):
    """Raised when a feature asks the registry for an unregistered template."""

    template_name: str

    def __str__(self) -> str:
        return f"Unknown email template: {self.template_name!r}"


@dataclass(frozen=True, slots=True)
class TemplateRenderError(EmailError):
    """Raised when Jinja2 fails to render a template (missing variable, etc.)."""

    template_name: str
    reason: str

    def __str__(self) -> str:
        return f"Failed to render template {self.template_name!r}: {self.reason}"


@dataclass(frozen=True, slots=True)
class DeliveryError(EmailError):
    """Raised when the wired adapter fails to dispatch the message."""

    reason: str

    def __str__(self) -> str:
        return f"Email delivery failed: {self.reason}"
