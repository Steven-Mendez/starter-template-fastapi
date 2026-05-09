from __future__ import annotations

from dataclasses import dataclass

from src.features.auth.application.crypto import PasswordService
from src.features.auth.application.errors import DuplicateEmailError, NotFoundError
from src.features.auth.application.normalization import (
    normalize_email,
    normalize_role_name,
)
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.domain.models import User
from src.platform.config.settings import AppSettings
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class RegisterUser:
    """Create a new user account and assign the default role."""

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
        default_role = self._repository.get_role_by_name(
            normalize_role_name(self._settings.auth_default_user_role)
        )
        if (
            default_role is not None
            and default_role.name != self._settings.auth_super_admin_role
        ):
            self._repository.assign_user_role(user.id, default_role.id)
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
