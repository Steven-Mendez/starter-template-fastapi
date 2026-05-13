from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.cache import PrincipalCachePort
from features.authentication.application.crypto import hash_token
from features.authentication.application.errors import AuthError, InvalidTokenError
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from features.users.application.ports.user_port import UserPort

EMAIL_VERIFY_PURPOSE = "email_verify"


@dataclass(slots=True)
class ConfirmEmailVerification:
    """Consume an email-verification token and mark the user as verified."""

    _users: UserPort
    _repository: AuthRepositoryPort
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        *,
        token: str,
    ) -> Result[None, AuthError]:
        record = self._repository.get_internal_token(
            token_hash=hash_token(token), purpose=EMAIL_VERIFY_PURPOSE
        )
        if (
            record is None
            or record.used_at is not None
            or record.expires_at <= datetime.now(UTC)
        ):
            return Err(InvalidTokenError("Invalid token"))
        if record.user_id is None:
            return Err(InvalidTokenError("Invalid token"))

        self._users.mark_verified(record.user_id)
        self._repository.mark_internal_token_used(record.id)
        if self._cache is not None:
            self._cache.invalidate_user(record.user_id)
        self._repository.record_audit_event(
            event_type="auth.email_verified",
            user_id=record.user_id,
        )
        return Ok(None)
