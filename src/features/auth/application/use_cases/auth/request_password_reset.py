from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.features.auth.application.crypto import generate_opaque_token, hash_token
from src.features.auth.application.errors import AuthError
from src.features.auth.application.normalization import normalize_email
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.types import InternalTokenResult
from src.platform.config.settings import AppSettings
from src.platform.shared.result import Ok, Result

PASSWORD_RESET_PURPOSE = "password_reset"


@dataclass(slots=True)
class RequestPasswordReset:
    """Create a password-reset token for the given email, if the account exists."""

    _repository: AuthRepositoryPort
    _settings: AppSettings

    def execute(
        self,
        *,
        email: str,
        ip_address: str | None = None,
    ) -> Result[InternalTokenResult, AuthError]:
        user = self._repository.get_user_by_email(normalize_email(email))
        if user is None:
            return Ok(InternalTokenResult(token=None, expires_at=None))

        raw_token = generate_opaque_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.auth_password_reset_token_expire_minutes
        )
        self._repository.create_internal_token(
            user_id=user.id,
            purpose=PASSWORD_RESET_PURPOSE,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
            created_ip=ip_address,
        )
        self._repository.record_audit_event(
            event_type="auth.password_reset_requested",
            user_id=user.id,
            ip_address=ip_address,
        )
        return Ok(
            InternalTokenResult(
                token=raw_token if self._settings.auth_return_internal_tokens else None,
                expires_at=expires_at,
            )
        )
