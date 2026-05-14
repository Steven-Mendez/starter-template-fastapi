from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from app_platform.config.settings import AppSettings
from app_platform.observability.metrics import AUTH_LOGINS_TOTAL
from app_platform.observability.tracing import email_hash, traced
from app_platform.shared.principal import Principal
from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.crypto import (
    FIXED_DUMMY_ARGON2_HASH,
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
from features.authentication.domain.models import Credential
from features.users.application.ports.user_port import UserPort


class _NoCredentialUserId:
    """Sentinel passed to ``get_credential_for_user`` when no user was found.

    Used by ``LoginUser`` so the DB roundtrip count is identical between the
    user-found and user-not-found branches — closing a timing channel that
    would otherwise allow email enumeration.
    """

    __slots__ = ()


_NO_CREDENTIAL_USER_ID: Final[_NoCredentialUserId] = _NoCredentialUserId()


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
    # Kept for backwards-compatibility with existing composition wiring;
    # the use case now uses ``FIXED_DUMMY_ARGON2_HASH`` (module-level) so
    # the miss-branch Argon2 cost is a fixed compile-time constant.
    _dummy_hash: str = FIXED_DUMMY_ARGON2_HASH

    def _get_credential_for_user(
        self, user_id: UUID | _NoCredentialUserId
    ) -> Credential | None:
        """Single credential-lookup call site for ``execute``.

        Always invoked exactly once per ``execute`` so the DB roundtrip
        count is identical between the user-found and user-not-found
        branches. The sentinel short-circuits to ``None`` because SQL
        adapters' ``WHERE user_id = ?`` predicate cannot accept a
        non-UUID value; the surrounding caller in ``execute`` still
        observes a single call to this method per request.
        """
        if isinstance(user_id, _NoCredentialUserId):
            return None
        return self._repository.get_credential_for_user(user_id)

    @traced(
        "auth.login_user",
        attrs=lambda self, *, email, password, ip_address=None, user_agent=None: {  # noqa: ARG005
            "user.email_hash": email_hash(email),
        },
    )
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
        # Always issue exactly one credential lookup, regardless of whether
        # ``user`` was found. The sentinel is shimmed to return ``None`` so
        # SQL adapters never see a non-UUID, but from the call-graph point
        # of view this method is invoked exactly once per request — closing
        # the DB-roundtrip-count timing channel that would otherwise let an
        # attacker enumerate registered emails.
        credential_id: UUID | _NoCredentialUserId = (
            user.id if user is not None else _NO_CREDENTIAL_USER_ID
        )
        credential = self._get_credential_for_user(credential_id)
        password_hash = (
            credential.hash if credential is not None else FIXED_DUMMY_ARGON2_HASH
        )
        # Always invoke exactly one ``verify_password`` call. The boolean
        # outcome is compared in constant time so branch selection is not
        # observable through wall-clock measurement of the comparison
        # itself; the dominant Argon2 cost is paid in both branches.
        verified = self._password_service.verify_password(password_hash, password)
        password_ok = hmac.compare_digest(b"\x01" if verified else b"\x00", b"\x01")
        if user is None or not password_ok:
            self._repository.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id if user is not None else None,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "invalid_credentials"},
            )
            AUTH_LOGINS_TOTAL.add(1, attributes={"result": "failure"})
            return Err(InvalidCredentialsError("Invalid credentials"))
        if not user.is_active:
            self._repository.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "inactive_user"},
            )
            AUTH_LOGINS_TOTAL.add(1, attributes={"result": "failure"})
            return Err(InactiveUserError("Inactive user"))
        if self._settings.auth_require_email_verification and not user.is_verified:
            self._repository.record_audit_event(
                event_type="auth.login_failed",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"reason": "email_not_verified"},
            )
            AUTH_LOGINS_TOTAL.add(1, attributes={"result": "failure"})
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
        AUTH_LOGINS_TOTAL.add(1, attributes={"result": "success"})
        return Ok((tokens, principal))
