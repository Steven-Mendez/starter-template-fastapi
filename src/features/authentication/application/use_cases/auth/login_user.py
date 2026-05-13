from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app_platform.config.settings import AppSettings
from app_platform.shared.principal import Principal
from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.crypto import (
    PasswordService,
    generate_opaque_token,
    hash_token,
)
from features.authentication.application.errors import (
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
)
from features.authentication.application.jwt_tokens import AccessTokenService
from features.authentication.application.normalization import normalize_email
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from features.authentication.application.types import IssuedTokens
from features.users.application.ports.user_port import UserPort


def _principal_from_user(user: object) -> Principal:
    return Principal(
        user_id=user.id,  # type: ignore[attr-defined]
        email=user.email,  # type: ignore[attr-defined]
        is_active=user.is_active,  # type: ignore[attr-defined]
        is_verified=user.is_verified,  # type: ignore[attr-defined]
        authz_version=user.authz_version,  # type: ignore[attr-defined]
    )


@dataclass(slots=True)
class LoginUser:
    """Authenticate credentials and issue a token pair."""

    _users: UserPort
    _repository: AuthRepositoryPort
    _password_service: PasswordService
    _token_service: AccessTokenService
    _settings: AppSettings
    _dummy_hash: str

    def execute(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Result[
        tuple[IssuedTokens, Principal],
        InvalidCredentialsError | InactiveUserError | EmailNotVerifiedError,
    ]:
        normalized_email = normalize_email(email)
        user = self._users.get_by_email(normalized_email)
        if user is None:
            self._password_service.verify_password(self._dummy_hash, password)
            self._repository.record_audit_event(
                event_type="auth.login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "invalid_credentials"},
            )
            return Err(InvalidCredentialsError("Invalid credentials"))
        credential = self._repository.get_credential_for_user(user.id)
        password_hash = credential.hash if credential is not None else self._dummy_hash
        if not self._password_service.verify_password(password_hash, password):
            self._repository.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "invalid_credentials"},
            )
            return Err(InvalidCredentialsError("Invalid credentials"))
        if not user.is_active:
            self._repository.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "inactive_user"},
            )
            return Err(InactiveUserError("Inactive user"))
        if self._settings.auth_require_email_verification and not user.is_verified:
            self._repository.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "email_not_verified"},
            )
            return Err(EmailNotVerifiedError("Email not verified"))
        self._users.update_last_login(user.id, datetime.now(UTC))
        principal = _principal_from_user(user)
        access_token, expires_in = self._token_service.issue(
            subject=user.id,
            authz_version=principal.authz_version,
        )
        raw_refresh = generate_opaque_token()
        self._repository.create_refresh_token(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            family_id=uuid4(),
            expires_at=datetime.now(UTC)
            + timedelta(days=self._settings.auth_refresh_token_expire_days),
            created_ip=ip_address,
            user_agent=user_agent,
        )
        self._repository.record_audit_event(
            event_type="auth.login_succeeded",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        tokens = IssuedTokens(
            access_token=access_token,
            refresh_token=raw_refresh,
            token_type="bearer",  # noqa: S106 — OAuth token-type identifier
            expires_in=expires_in,
        )
        return Ok((tokens, principal))
