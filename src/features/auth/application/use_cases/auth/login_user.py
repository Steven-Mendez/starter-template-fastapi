from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.features.auth.application.crypto import (
    PasswordService,
    generate_opaque_token,
    hash_token,
)
from src.features.auth.application.errors import (
    EmailNotVerifiedError,
    InactiveUserError,
    InvalidCredentialsError,
)
from src.features.auth.application.jwt_tokens import AccessTokenService
from src.features.auth.application.normalization import normalize_email
from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.auth.application.types import IssuedTokens
from src.platform.config.settings import AppSettings
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class LoginUser:
    """Authenticate credentials and issue a token pair."""

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
        user = self._repository.get_user_by_email(normalized_email)
        if user is None:
            self._password_service.verify_password(self._dummy_hash, password)
            self._repository.record_audit_event(
                event_type="auth.login_failed",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "invalid_credentials"},
            )
            return Err(InvalidCredentialsError("Invalid credentials"))
        if not self._password_service.verify_password(user.password_hash, password):
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
        self._repository.update_user_login(user.id, datetime.now(timezone.utc))
        principal = self._repository.get_principal(user.id)
        if principal is None:
            return Err(InvalidCredentialsError("Invalid credentials"))
        access_token, expires_in = self._token_service.issue(
            subject=user.id,
            roles=set(principal.roles),
            authz_version=principal.authz_version,
        )
        raw_refresh = generate_opaque_token()
        self._repository.create_refresh_token(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            family_id=uuid4(),
            expires_at=datetime.now(timezone.utc)
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
            token_type="bearer",
            expires_in=expires_in,
        )
        return Ok((tokens, principal))
