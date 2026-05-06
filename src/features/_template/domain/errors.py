from __future__ import annotations

from enum import StrEnum


class TemplateDomainError(StrEnum):
    """Domain failures for the copied feature, without HTTP coupling."""

    NOT_FOUND = "not_found"
