from __future__ import annotations

from enum import StrEnum


class TemplateDomainError(StrEnum):
    """TODO(template): one variant per domain failure mode (no HTTP coupling)."""

    NOT_FOUND = "not_found"
