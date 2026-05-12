"""Application-layer errors for the users feature."""

from __future__ import annotations

from enum import Enum


class UserError(Enum):
    """Closed enumeration of user-related failures returned via :class:`Result`."""

    DUPLICATE_EMAIL = "duplicate_email"
    NOT_FOUND = "not_found"
