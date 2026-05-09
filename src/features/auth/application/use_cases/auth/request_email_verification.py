from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from src.features.auth.application.crypto import generate_opaque_token, hash_token
from src.features.auth.application.errors import AuthError, NotFoundError
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.types import InternalTokenResult
from src.platform.config.settings import AppSettings
from src.platform.shared.result import Err, Ok, Result

EMAIL_VERIFY_PURPOSE = "email_verify"


@dataclass(slots=True)
class RequestEmailVerification:
    """Create an email-verification token for an authenticated user."""

    _repository: AuthRepositoryPort
    _settings: AppSettings

    def execute(
        self,
        *,
        user_id: UUID,
        ip_address: str | None = None,
    ) -> Result[InternalTokenResult, AuthError]:
        user = self._repository.get_user_by_id(user_id)
        if user is None:
            return Err(NotFoundError("User not found"))

        raw_token = generate_opaque_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.auth_email_verify_token_expire_minutes
        )
        self._repository.create_internal_token(
            user_id=user.id,
            purpose=EMAIL_VERIFY_PURPOSE,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
            created_ip=ip_address,
        )
        self._repository.record_audit_event(
            event_type="auth.email_verify_requested",
            user_id=user.id,
            ip_address=ip_address,
        )
        return Ok(
            InternalTokenResult(
                token=raw_token if self._settings.auth_return_internal_tokens else None,
                expires_at=expires_at,
            )
        )
