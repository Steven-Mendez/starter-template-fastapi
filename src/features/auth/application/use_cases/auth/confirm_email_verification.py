from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from src.features.auth.application.cache import PrincipalCachePort
from src.features.auth.application.crypto import hash_token
from src.features.auth.application.errors import AuthError, InvalidTokenError
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.platform.shared.result import Err, Ok, Result

EMAIL_VERIFY_PURPOSE = "email_verify"


@dataclass(slots=True)
class ConfirmEmailVerification:
    """Consume an email-verification token and mark the user as verified."""

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
            or record.expires_at <= datetime.now(timezone.utc)
        ):
            return Err(InvalidTokenError("Invalid token"))
        if record.user_id is None:
            return Err(InvalidTokenError("Invalid token"))

        self._repository.set_user_verified(record.user_id)
        self._repository.mark_internal_token_used(record.id)
        if self._cache is not None:
            self._cache.invalidate_user(record.user_id)
        self._repository.record_audit_event(
            event_type="auth.email_verified",
            user_id=record.user_id,
        )
        return Ok(None)
