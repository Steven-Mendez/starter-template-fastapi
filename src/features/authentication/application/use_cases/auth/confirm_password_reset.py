from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
from features.users.application.ports.user_port import UserPort

PASSWORD_RESET_PURPOSE = "password_reset"


@dataclass(slots=True)
class ConfirmPasswordReset:
    """Apply a new password and invalidate all existing sessions.

    Atomicity story: token consumption + refresh-token revocation share a
    single transaction guarded by ``SELECT FOR UPDATE`` on the token row,
    so concurrent confirmations serialize. The password update itself
    runs in a separate users-feature transaction *before* the token is
    marked used; a crash between those two commits is benign because the
    new password is idempotent and the token row's ``FOR UPDATE`` lock
    still excludes other consumers until the request finishes.
    """

    _users: UserPort
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
                # Credential write goes to authentication's own table.
                # Cache invalidation still flows through users via
                # ``bump_authz_version``. The FOR UPDATE lock on the
                # token row keeps concurrent confirmations from
                # interleaving even though both writes commit in their
                # own transactions.
                self._repository.upsert_credential(
                    user_id=user_id,
                    algorithm="argon2",
                    hash=self._password_service.hash_password(new_password),
                )
                self._users.bump_authz_version(user_id)
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
