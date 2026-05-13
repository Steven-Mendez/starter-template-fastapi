from __future__ import annotations

from dataclasses import dataclass

from app_platform.config.settings import AppSettings
from app_platform.observability.tracing import email_hash, traced
from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.crypto import PasswordService
from features.authentication.application.errors import (
    DuplicateEmailError,
    NotFoundError,
)
from features.authentication.application.normalization import normalize_email
from features.authentication.application.ports.outbound.auth_repository import (
    AuditRepositoryPort,
    CredentialRepositoryPort,
)
from features.users.application.errors import UserAlreadyExistsError
from features.users.application.ports.user_port import UserPort
from features.users.domain.user import User


@dataclass(slots=True)
class RegisterUser:
    """Create a new user account.

    Orchestration use case: hashes the password locally, asks the users
    feature to persist the account via :class:`UserPort`, writes the
    hash into authentication's own ``credentials`` table, and records a
    ``auth.user_registered`` audit event.

    Under ReBAC, registration does not assign a default role: a freshly
    registered user holds no relationship tuples and therefore has no
    access to any resource. Access is granted explicitly afterwards.
    """

    _users: UserPort
    _credentials: CredentialRepositoryPort
    _audit: AuditRepositoryPort
    _password_service: PasswordService
    _settings: AppSettings

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
        password_hash = self._password_service.hash_password(password)
        result = self._users.create(email=normalized_email)
        match result:
            case Err(error=err):
                if isinstance(err, UserAlreadyExistsError):
                    return Err(DuplicateEmailError("Email already registered"))
                return Err(NotFoundError("User not found after registration"))
            case Ok(value=user):
                self._credentials.upsert_credential(
                    user_id=user.id,
                    algorithm="argon2",
                    hash=password_hash,
                )
                self._audit.record_audit_event(
                    event_type="auth.user_registered",
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                return Ok(user)
