"""Application errors raised inside the outbox feature.

The dispatch use case wraps adapter failures in :class:`OutboxDispatchError`
so callers (the relay registration in the worker) can log a stable
type without depending on whichever backend raised the original
exception.
"""

from __future__ import annotations

from app_platform.shared.errors import ApplicationError


class OutboxError(ApplicationError):
    """Base class for outbox application errors."""


class OutboxDispatchError(OutboxError):
    """The relay tick failed to dispatch one or more rows.

    The dispatch use case itself records per-row outcomes back to the
    repository (retry / failed); this exception is only raised when
    the relay's own bookkeeping fails (e.g. the DB write to mark a
    row as dispatched raised).
    """
