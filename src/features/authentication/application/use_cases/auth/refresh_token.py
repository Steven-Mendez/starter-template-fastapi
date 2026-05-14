from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app_platform.config.settings import AppSettings
from app_platform.observability.metrics import AUTH_REFRESH_TOTAL
from app_platform.shared.principal import Principal
from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.crypto import (
    generate_opaque_token,
    hash_token,
)
from features.authentication.application.errors import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from features.authentication.application.jwt_tokens import AccessTokenService
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from features.authentication.application.types import IssuedTokens
from features.users.application.dto import UserSnapshot
from features.users.application.ports.user_port import UserPort


def _principal_from_user(user: UserSnapshot) -> Principal:
    return Principal(
        user_id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_verified=user.is_verified,
        authz_version=user.authz_version,
    )


@dataclass(slots=True)
class RotateRefreshToken:
    """Rotate a refresh token and issue a new token pair."""

    _users: UserPort
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
        # Single-exit wrapper around ``_execute`` so the
        # ``app_auth_refresh_total`` counter is incremented EXACTLY once
        # per call, regardless of which branch returns. ``_execute``
        # contains the original early-return control flow unchanged.
        result = self._execute(
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        AUTH_REFRESH_TOTAL.add(
            1,
            attributes={"result": "success" if isinstance(result, Ok) else "failure"},
        )
        return result

    def _execute(
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

            now = datetime.now(UTC)
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
                user = self._users.get_by_id(record.user_id)
                if user is None:
                    return Err(InvalidCredentialsError("Invalid credentials"))
                if not user.is_active:
                    return Err(InactiveUserError("Inactive user"))
                principal = _principal_from_user(user)

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
                    token_type="bearer",  # noqa: S106 — OAuth token-type identifier
                    expires_in=expires_in,
                )

        if invalid_token_error is not None:
            return Err(invalid_token_error)
        if tokens is None or principal is None:
            return Err(InvalidTokenError("Invalid refresh token"))
        return Ok((tokens, principal))
