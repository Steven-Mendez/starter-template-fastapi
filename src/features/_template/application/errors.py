"""Application-layer errors returned by use cases."""

from __future__ import annotations

from enum import Enum


class ApplicationError(Enum):
    """Closed enumeration of failure modes returned via :class:`Result`."""

    NOT_FOUND = "not_found"
    NAME_REQUIRED = "name_required"
    FORBIDDEN = "forbidden"
