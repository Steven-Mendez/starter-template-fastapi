from __future__ import annotations

from dataclasses import dataclass

from src.features.authentication.application.crypto import PasswordService
from src.features.authentication.application.errors import (
    DuplicateEmailError,
    NotFoundError,
)
from src.features.authentication.application.normalization import normalize_email
from src.features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.authentication.domain.models import User
from src.platform.config.settings import AppSettings
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class RegisterUser:
    """Create a new user account.

    Under ReBAC, registration does not assign a default role: a freshly
    registered user holds no relationship tuples and therefore has no
    access to any resource. Access is granted explicitly afterwards
    (typically by a system admin or by the user creating their own
    resources, in which case they receive the owner relation).
    """

    _repository: AuthRepositoryPort
    _password_service: PasswordService
    _settings: AppSettings

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
        user = self._repository.create_user(
            email=normalized_email, password_hash=password_hash
        )
        if user is None:
            return Err(DuplicateEmailError("Email already registered"))
        self._repository.record_audit_event(
            event_type="auth.user_registered",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        fresh = self._repository.get_user_by_id(user.id)
        if fresh is None:
            return Err(NotFoundError("User not found after registration"))
        return Ok(fresh)
