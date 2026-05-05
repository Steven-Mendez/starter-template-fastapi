from __future__ import annotations

from enum import StrEnum


class ApplicationError(StrEnum):
    """TODO(template): application errors (mapped to HTTP by the inbound adapter)."""

    NOT_FOUND = ("not_found", "Resource not found")

    _detail: str

    def __new__(cls, value: str, detail: str) -> ApplicationError:
        member = str.__new__(cls, value)
        member._value_ = value
        member._detail = detail
        return member

    @property
    def detail(self) -> str:
        return self._detail
