"""Domain-level exceptions raised by the :mod:`_template.domain` package."""

from __future__ import annotations


class TemplateDomainError(Exception):
    """Base class for domain-level errors in the template feature."""


class ThingNameRequiredError(TemplateDomainError):
    """Raised when a :class:`Thing` is created or renamed with an empty name."""
