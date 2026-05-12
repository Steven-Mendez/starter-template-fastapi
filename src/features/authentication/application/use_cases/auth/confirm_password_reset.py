from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from src.features.authentication.application.cache import PrincipalCachePort
from src.features.authentication.application.crypto import PasswordService, hash_token
from src.features.authentication.application.errors import (
    AuthError,
    InvalidTokenError,
    TokenAlreadyUsedError,
)
from src.features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.platform.shared.result import Err, Ok, Result

PASSWORD_RESET_PURPOSE = "password_reset"


@dataclass(slots=True)
class ConfirmPasswordReset:
    """Apply a new password and invalidate all existing sessions."""

    _repository: AuthRepositoryPort
    _password_service: PasswordService
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        *,
        token: str,
        new_password: str,
    ) -> Result[None, AuthError]:
        user_id: UUID | None = None
        error: InvalidTokenError | TokenAlreadyUsedError | None = None

        with self._repository.internal_token_transaction() as tx:
            record = tx.get_internal_token_for_update(
                token_hash=hash_token(token), purpose=PASSWORD_RESET_PURPOSE
            )
            if record is None or record.expires_at <= datetime.now(timezone.utc):
                error = InvalidTokenError("Invalid token")
            elif record.used_at is not None:
                error = TokenAlreadyUsedError("Token already used")
            elif record.user_id is None:
                error = InvalidTokenError("Invalid token")
            else:
                user_id = record.user_id
                tx.update_user_password(
                    user_id, self._password_service.hash_password(new_password)
                )
                tx.mark_internal_token_used(record.id)
                tx.revoke_user_refresh_tokens(user_id)
                tx.record_audit_event(
                    event_type="auth.password_reset_completed",
                    user_id=user_id,
                )

        if error is not None:
            return Err(error)
        if user_id is not None and self._cache is not None:
            self._cache.invalidate_user(user_id)
        return Ok(None)
