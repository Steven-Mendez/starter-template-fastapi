"""Authorization-specific application errors."""

from __future__ import annotations

from src.features.auth.application.errors import AuthError


class NotAuthorizedError(AuthError):
    """Raised when a principal is not authorized to perform the requested action."""


class UnknownActionError(AuthError):
    """Raised when an (resource_type, action) pair has no defined relation set.

    Typically a programmer error: every action mounted on a route must have a
    matching entry in ``application/authorization/actions.py``.
    """
