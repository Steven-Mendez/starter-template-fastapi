from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.features.auth.application.crypto import generate_opaque_token, hash_token
from src.features.auth.application.errors import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from src.features.auth.application.jwt_tokens import AccessTokenService
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.types import IssuedTokens
from src.platform.config.settings import AppSettings
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class RotateRefreshToken:
    """Rotate a refresh token and issue a new token pair."""

    _repository: AuthRepositoryPort
    _token_service: AccessTokenService
    _settings: AppSettings

    def execute(
        self,
        *,
        refresh_token: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[
        tuple[IssuedTokens, Principal],
        InvalidTokenError | InvalidCredentialsError | InactiveUserError,
    ]:
        if not refresh_token:
            return Err(InvalidTokenError("Invalid refresh token"))

        invalid_token_error: InvalidTokenError | None = None
        tokens: IssuedTokens | None = None
        principal: Principal | None = None

        with self._repository.refresh_token_transaction() as tx:
            record = tx.get_refresh_token_for_update(hash_token(refresh_token))
            if record is None:
                return Err(InvalidTokenError("Invalid refresh token"))

            now = datetime.now(timezone.utc)
            if record.revoked_at is not None:
                tx.revoke_refresh_family(record.family_id)
                tx.record_audit_event(
                    event_type="auth.refresh_reuse_detected",
                    user_id=record.user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata={"family_id": str(record.family_id)},
                )
                invalid_token_error = InvalidTokenError("Invalid refresh token")
            elif record.expires_at <= now:
                tx.revoke_refresh_token(record.id)
                invalid_token_error = InvalidTokenError("Invalid refresh token")
            else:
                principal = tx.get_principal(record.user_id)
                if principal is None:
                    return Err(InvalidCredentialsError("Invalid credentials"))
                if not principal.is_active:
                    return Err(InactiveUserError("Inactive user"))

                access_token, expires_in = self._token_service.issue(
                    subject=record.user_id,
                    authz_version=principal.authz_version,
                )
                raw_refresh = generate_opaque_token()
                replacement = tx.create_refresh_token(
                    user_id=record.user_id,
                    token_hash=hash_token(raw_refresh),
                    family_id=record.family_id,
                    expires_at=now
                    + timedelta(days=self._settings.auth_refresh_token_expire_days),
                    created_ip=ip_address,
                    user_agent=user_agent,
                )
                tx.revoke_refresh_token(
                    record.id,
                    replaced_by_token_id=replacement.id,
                )
                tx.record_audit_event(
                    event_type="auth.refresh_succeeded",
                    user_id=record.user_id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                tokens = IssuedTokens(
                    access_token=access_token,
                    refresh_token=raw_refresh,
                    token_type="bearer",
                    expires_in=expires_in,
                )

        if invalid_token_error is not None:
            return Err(invalid_token_error)
        if tokens is None or principal is None:
            return Err(InvalidTokenError("Invalid refresh token"))
        return Ok((tokens, principal))
