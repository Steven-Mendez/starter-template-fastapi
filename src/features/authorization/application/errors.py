"""Authorization-specific application errors.

These do NOT inherit from the auth feature's ``AuthError`` because the
authorization feature must not import from auth. The platform layer
maps :class:`AuthorizationError` subclasses to HTTP responses via an
exception handler registered from the authorization feature's wiring.
"""

from __future__ import annotations

from uuid import UUID

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


class CredentialVerificationError(AuthorizationError):
    """Raised by ``CredentialVerifierPort`` on a non-matching credential.

    Carries the ``user_id`` so call sites (today: ``BootstrapSystemAdmin``)
    can log structured remediation hints without re-reading the user
    row. The error itself does not distinguish "no credential row" from
    "wrong password" — both reduce to "operator did not supply the
    correct password for this user" at the caller's level of concern.
    """

    def __init__(self, user_id: UUID) -> None:
        super().__init__(f"credential verification failed for user_id={user_id}")
        self.user_id = user_id

    def __reduce__(self) -> tuple[type[CredentialVerificationError], tuple[UUID]]:
        return (type(self), (self.user_id,))


class BootstrapRefusedExistingUserError(AuthorizationError):
    """Refusal to promote an existing non-admin account without opt-in.

    Raised by ``BootstrapSystemAdmin`` when the configured email
    resolves to a user who already exists but does NOT hold
    ``system:main#admin`` and ``APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING`` is
    not set. The default-deny posture prevents accidental privilege
    escalation when an attacker (or any unrelated user) self-registered
    with the configured admin email before the deploy.
    """

    def __init__(self, user_id: UUID, email: str) -> None:
        super().__init__(
            f"refusing to bootstrap system admin: user_id={user_id} "
            f"email={email} already exists and is not a system admin; "
            f"set APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true to opt in"
        )
        self.user_id = user_id
        self.email = email

    def __reduce__(
        self,
    ) -> tuple[type[BootstrapRefusedExistingUserError], tuple[UUID, str]]:
        return (type(self), (self.user_id, self.email))


class BootstrapPasswordMismatchError(AuthorizationError):
    """Refusal to promote because the supplied bootstrap password is wrong.

    Raised by ``BootstrapSystemAdmin`` when
    ``APP_AUTH_BOOTSTRAP_PROMOTE_EXISTING=true`` but the supplied
    password does not match the existing user's stored credential.
    """

    def __init__(self, user_id: UUID) -> None:
        super().__init__(
            f"bootstrap password did not match existing user's credential "
            f"(user_id={user_id})"
        )
        self.user_id = user_id

    def __reduce__(
        self,
    ) -> tuple[type[BootstrapPasswordMismatchError], tuple[UUID]]:
        return (type(self), (self.user_id,))
