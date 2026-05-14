"""Domain errors raised by the auth and RBAC services.

All errors inherit from :class:`AuthError` so the HTTP layer can catch a
single base type and delegate the mapping to ``raise_http_from_auth_error``,
keeping internal error classes from leaking into routers.
"""

from __future__ import annotations

from app_platform.shared.errors import ApplicationError


class AuthError(ApplicationError):
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
    """Raised when auth endpoint attempts exceed the per-window limit.

    Carries ``retry_after_seconds`` so the HTTP layer can set the RFC 7231
    §7.1.3 ``Retry-After`` header on the 429 response. The value is computed
    by the rate-limit dependency from the limiter's window size, since the
    HTTP error mapping does not have access to the limiter configuration.
    """

    def __init__(self, message: str, retry_after_seconds: int) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds

    def __reduce__(
        self,
    ) -> tuple[type[RateLimitExceededError], tuple[str, int]]:
        # Custom reduce so the error round-trips through pickle (and therefore
        # the arq Redis boundary): ``Exception.__reduce__`` only carries
        # ``self.args`` and would drop ``retry_after_seconds``.
        return (type(self), (self.args[0], self.retry_after_seconds))
