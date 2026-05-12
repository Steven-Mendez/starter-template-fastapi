"""Domain errors raised by the auth and RBAC services.

All errors inherit from :class:`AuthError` so the HTTP layer can catch a
single base type and delegate the mapping to ``raise_http_from_auth_error``,
keeping internal error classes from leaking into routers.
"""

from __future__ import annotations


class AuthError(RuntimeError):
    """Base class for every expected auth or RBAC failure."""


class DuplicateEmailError(AuthError):
    """Raised when an email is already registered to another account."""


class InvalidCredentialsError(AuthError):
    """Raised when login fails for unknown email, wrong password, or inactive account.

    The same error is used for all three cases on purpose so the API does
    not reveal whether a given email exists.
    """


class InvalidTokenError(AuthError):
    """Raised when a token is missing, malformed, expired, or otherwise unusable."""


class StaleTokenError(InvalidTokenError):
    """Raised when a token is valid structurally but its authz snapshot is stale.

    Subclassing :class:`InvalidTokenError` keeps the HTTP mapping at 401 while
    allowing fine-grained logging and future client-side differentiation
    (for example, "re-login required" vs "token signature invalid").
    """


class InactiveUserError(AuthError):
    """Raised when an authenticated request targets a user that has been deactivated."""


class EmailNotVerifiedError(AuthError):
    """Raised when email verification is required before authentication."""


class PermissionDeniedError(AuthError):
    """Raised when a principal lacks the roles or permissions for an action."""


class TokenAlreadyUsedError(AuthError):
    """Raised when a single-use internal token was already consumed."""


class NotFoundError(AuthError):
    """Raised when a referenced auth/RBAC entity does not exist."""


class ConflictError(AuthError):
    """Raised when a mutation breaks uniqueness or naming rules."""


class ConfigurationError(AuthError):
    """Raised when a required configuration value (such as the JWT secret) is missing.

    Surfaces misconfiguration at the call site rather than producing tokens
    that no deployment can verify.
    """


class RateLimitExceededError(AuthError):
    """Raised when auth endpoint attempts exceed the per-window limit."""
