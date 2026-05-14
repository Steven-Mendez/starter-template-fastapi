from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Ok, Result
from features.authentication.application.crypto import (
    FIXED_DUMMY_ARGON2_HASH,
    PasswordService,
    generate_opaque_token,
    hash_token,
)
from features.authentication.application.errors import AuthError
from features.authentication.application.normalization import normalize_email
from features.authentication.application.ports.outbound.auth_repository import (
    TokenRepositoryPort,
)
from features.authentication.application.types import InternalTokenResult
from features.authentication.email_templates import PASSWORD_RESET_TEMPLATE
from features.email.application.jobs import SEND_EMAIL_JOB
from features.users.application.ports.user_port import UserPort

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RequestPasswordReset:
    """Create a password-reset token for the given email, if the account exists.

    Token issuance, audit event, and the ``send_email`` outbox row all
    commit inside a single ``issue_internal_token_transaction`` — so a
    rollback in any one of them drops the entire side effect. The
    relay running in the worker picks up the outbox row and dispatches
    the email through ``JobQueuePort``.
    """

    _users: UserPort
    _repository: TokenRepositoryPort
    _password_service: PasswordService
    _settings: AppSettings

    def execute(
        self,
        *,
        email: str,
        ip_address: str | None = None,
    ) -> Result[InternalTokenResult, AuthError]:
        user = self._users.get_by_email(normalize_email(email))
        if user is None:
            # Pay the dominant Argon2 wall-clock cost so the unknown-email
            # branch is not enumerable by timing the response. The boolean
            # result is discarded; passing ``email`` as the candidate
            # plaintext is intentional — only the Argon2 verify cost
            # matters here, not the comparison outcome.
            self._password_service.verify_password(FIXED_DUMMY_ARGON2_HASH, email)
            return Ok(InternalTokenResult(token=None, expires_at=None))

        # Known-email branch also pays exactly one Argon2-class verify so
        # both branches share the same dominant wall-clock cost. Without
        # this, the known branch (audit + token writes + outbox enqueue,
        # ~7 ms) is markedly *faster* than the unknown branch (full
        # Argon2 verify, ~30-40 ms), inverting the timing channel. The
        # boolean result is discarded; only the wall-clock cost matters.
        self._password_service.verify_password(FIXED_DUMMY_ARGON2_HASH, email)

        raw_token = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(
            minutes=self._settings.auth_password_reset_token_expire_minutes
        )
        with self._repository.issue_internal_token_transaction() as tx:
            # Stamp ``used_at = now()`` on any prior unused
            # password-reset tokens for this user *before* inserting the
            # new one, inside the same transaction. This closes the
            # phishing surface where a captured older email retains a
            # live token after the user clicks "Send again".
            tx.invalidate_unused_tokens_for(user.id, "password_reset")
            tx.create_internal_token(
                user_id=user.id,
                purpose="password_reset",
                token_hash=hash_token(raw_token),
                expires_at=expires_at,
                created_ip=ip_address,
            )
            tx.record_audit_event(
                event_type="auth.password_reset_requested",
                user_id=user.id,
                ip_address=ip_address,
            )
            tx.outbox.enqueue(
                job_name=SEND_EMAIL_JOB,
                payload={
                    "to": user.email,
                    "template_name": PASSWORD_RESET_TEMPLATE,
                    "context": {
                        "app_name": self._settings.app_display_name,
                        "email": user.email,
                        "reset_url": _reset_url(
                            self._settings.app_public_url, raw_token
                        ),
                        "expires_in_minutes": (
                            self._settings.auth_password_reset_token_expire_minutes
                        ),
                    },
                },
            )

        return Ok(
            InternalTokenResult(
                token=raw_token if self._settings.auth_return_internal_tokens else None,
                expires_at=expires_at,
            )
        )


def _reset_url(public_url: str, token: str) -> str:
    return f"{public_url.rstrip('/')}/auth/password/reset?token={token}"
