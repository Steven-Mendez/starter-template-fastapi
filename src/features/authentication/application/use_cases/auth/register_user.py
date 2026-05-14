from __future__ import annotations

from dataclasses import dataclass

from app_platform.observability.tracing import email_hash, traced
from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.crypto import PasswordService
from features.authentication.application.errors import (
    DuplicateEmailError,
    NotFoundError,
)
from features.authentication.application.normalization import normalize_email
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from features.users.application.errors import UserAlreadyExistsError
from features.users.domain.user import User


@dataclass(slots=True)
class RegisterUser:
    """Create a new user account.

    Atomicity story: the three writes registration needs to perform —
    the ``User`` row, the ``Credential`` row in authentication's own
    ``credentials`` table, and the ``auth.user_registered`` audit
    event — commit in a single database transaction through
    ``register_user_transaction()``. A failure in any one of them
    rolls back the other two; a crash mid-write leaves the database
    in the pre-registration state and the email remains usable on
    the next attempt.

    Under ReBAC, registration does not assign a default role: a freshly
    registered user holds no relationship tuples and therefore has no
    access to any resource. Access is granted explicitly afterwards.
    """

    _repository: AuthRepositoryPort
    _password_service: PasswordService

    @traced(
        "auth.register_user",
        attrs=lambda self, *, email, password, ip_address=None, user_agent=None: {  # noqa: ARG005
            "user.email_hash": email_hash(email),
        },
    )
    def execute(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[User, DuplicateEmailError | NotFoundError]:
        normalized_email = normalize_email(email)
        # Hash the password outside the transaction: Argon2 is
        # intentionally CPU-bound and holding a DB transaction open
        # across the hash would inflate connection-pool contention.
        password_hash = self._password_service.hash_password(password)

        with self._repository.register_user_transaction() as tx:
            create_result = tx.create_user(email=normalized_email)
            match create_result:
                case Err(error=err):
                    if isinstance(err, UserAlreadyExistsError):
                        return Err(DuplicateEmailError("Email already registered"))
                    return Err(NotFoundError("User not found after registration"))
                case Ok(value=user):
                    tx.upsert_credential(
                        user_id=user.id,
                        algorithm="argon2",
                        hash=password_hash,
                    )
                    tx.record_audit_event(
                        event_type="auth.user_registered",
                        user_id=user.id,
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
                    return Ok(user)
