from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.cache import PrincipalCachePort
from features.authentication.application.crypto import PasswordService, hash_token
from features.authentication.application.errors import (
    AuthError,
    InvalidTokenError,
    TokenAlreadyUsedError,
)
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)

PASSWORD_RESET_PURPOSE = "password_reset"  # noqa: S105 — token purpose tag, not a credential


@dataclass(slots=True)
class ConfirmPasswordReset:
    """Apply a new password and invalidate all existing sessions.

    Atomicity story: credential upsert, reset-token consumption,
    refresh-token revocation, authz-version bump, and audit event
    all commit in a single transaction guarded by ``SELECT FOR
    UPDATE`` on the token row. A crash anywhere in the chain rolls
    back the credential update along with the token-consumption
    write, leaving the user's password unchanged and the token
    still consumable.
    """

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
        # Hash the new password before opening the transaction: Argon2
        # is CPU-bound and holding the FOR UPDATE lock across the hash
        # would serialize concurrent confirmations on the lock instead
        # of on the database snapshot.
        new_hash = self._password_service.hash_password(new_password)

        with self._repository.internal_token_transaction() as tx:
            record = tx.get_internal_token_for_update(
                token_hash=hash_token(token), purpose=PASSWORD_RESET_PURPOSE
            )
            if record is None or record.expires_at <= datetime.now(UTC):
                error = InvalidTokenError("Invalid token")
            elif record.used_at is not None:
                error = TokenAlreadyUsedError("Token already used")
            elif record.user_id is None:
                error = InvalidTokenError("Invalid token")
            else:
                user_id = record.user_id
                tx.upsert_credential(
                    user_id=user_id,
                    algorithm="argon2",
                    hash=new_hash,
                )
                tx.bump_user_authz_version(user_id)
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
