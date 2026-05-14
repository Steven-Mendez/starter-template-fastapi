from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.cache import PrincipalCachePort
from features.authentication.application.crypto import hash_token
from features.authentication.application.errors import (
    AuthError,
    InvalidTokenError,
    TokenAlreadyUsedError,
)
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)

EMAIL_VERIFY_PURPOSE = "email_verify"


@dataclass(slots=True)
class ConfirmEmailVerification:
    """Consume an email-verification token and mark the user as verified.

    Atomicity story: the token read uses ``SELECT FOR UPDATE`` so
    concurrent submissions of the same token serialize on the
    database row lock. The ``mark_user_verified``, ``mark_internal_token_used``,
    and audit-event writes all commit in the same transaction; a
    crash anywhere in the chain rolls back the verification flag
    along with the token consumption so a subsequent retry sees the
    pre-confirmation state.
    """

    _repository: AuthRepositoryPort
    _cache: PrincipalCachePort | None = None

    def execute(
        self,
        *,
        token: str,
    ) -> Result[None, AuthError]:
        user_id: UUID | None = None
        error: InvalidTokenError | TokenAlreadyUsedError | None = None

        with self._repository.internal_token_transaction() as tx:
            record = tx.get_internal_token_for_update(
                token_hash=hash_token(token), purpose=EMAIL_VERIFY_PURPOSE
            )
            if record is None or record.expires_at <= datetime.now(UTC):
                error = InvalidTokenError("Invalid token")
            elif record.used_at is not None:
                # Distinguish "consumed" from "unknown / expired" so callers
                # (and the integration suite that exercises re-issuance
                # invalidation) can react to the two cases independently.
                error = TokenAlreadyUsedError("Token already used")
            elif record.user_id is None:
                error = InvalidTokenError("Invalid token")
            else:
                user_id = record.user_id
                tx.mark_user_verified(user_id)
                tx.mark_internal_token_used(record.id)
                tx.record_audit_event(
                    event_type="auth.email_verified",
                    user_id=user_id,
                )

        if error is not None:
            return Err(error)
        # Cache invalidation runs outside the transaction so it only
        # fires after a successful commit.
        if user_id is not None and self._cache is not None:
            self._cache.invalidate_user(user_id)
        return Ok(None)
