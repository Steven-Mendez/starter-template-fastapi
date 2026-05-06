"""Closed enumeration of application failures for the template feature scaffold."""

from __future__ import annotations

from enum import StrEnum


class ApplicationError(StrEnum):
    """Application errors that the copied feature maps at its inbound edge."""

    NOT_FOUND = ("not_found", "Resource not found")

    _detail: str

    def __new__(cls, value: str, detail: str) -> ApplicationError:
        """Build a ``StrEnum`` member that also carries a ``detail`` attribute."""
        member = str.__new__(cls, value)
        member._value_ = value
        member._detail = detail
        return member

    @property
    def detail(self) -> str:
        """Return the human-readable description for this error."""
        return self._detail
