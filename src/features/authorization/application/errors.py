"""Authorization-specific application errors.

These do NOT inherit from the auth feature's ``AuthError`` because the
authorization feature must not import from auth. The platform layer
maps :class:`AuthorizationError` subclasses to HTTP responses via an
exception handler registered from the authorization feature's wiring.
"""

from __future__ import annotations

from app_platform.shared.errors import ApplicationError


class AuthorizationError(ApplicationError):
    """Base class for every expected authorization failure."""


class NotAuthorizedError(AuthorizationError):
    """Raised when a principal is not authorized to perform the requested action."""


class UnknownActionError(AuthorizationError):
    """Raised when an (resource_type, action) pair has no registered relation set.

    Typically a programmer error: every action mounted on a route must be
    declared on the ``AuthorizationRegistry`` by whichever feature owns
    the resource type. The HTTP layer maps this to 500 so the bug
    surfaces during integration testing rather than as a silent 403.
    """
