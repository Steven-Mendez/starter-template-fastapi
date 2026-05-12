from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from src.features.authentication.application.crypto import (
    generate_opaque_token,
    hash_token,
)
from src.features.authentication.application.errors import AuthError
from src.features.authentication.application.normalization import normalize_email
from src.features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from src.features.authentication.application.types import InternalTokenResult
from src.features.authentication.email_templates import PASSWORD_RESET_TEMPLATE
from src.features.background_jobs.application.errors import JobError
from src.features.background_jobs.application.ports.job_queue_port import JobQueuePort
from src.features.email.composition.jobs import SEND_EMAIL_JOB
from src.features.users.application.ports.user_port import UserPort
from src.platform.config.settings import AppSettings
from src.platform.shared.result import Ok, Result

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RequestPasswordReset:
    """Create a password-reset token for the given email, if the account exists."""

    _users: UserPort
    _repository: AuthRepositoryPort
    _jobs: JobQueuePort
    _settings: AppSettings

    def execute(
        self,
        *,
        email: str,
        ip_address: str | None = None,
    ) -> Result[InternalTokenResult, AuthError]:
        user = self._users.get_by_email(normalize_email(email))
        if user is None:
            return Ok(InternalTokenResult(token=None, expires_at=None))

        raw_token = generate_opaque_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.auth_password_reset_token_expire_minutes
        )
        self._repository.create_internal_token(
            user_id=user.id,
            purpose="password_reset",
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
            created_ip=ip_address,
        )
        self._repository.record_audit_event(
            event_type="auth.password_reset_requested",
            user_id=user.id,
            ip_address=ip_address,
        )

        # Don't fail the use case on enqueue errors: the token is already
        # issued and audited, and the API contract is 202 regardless of
        # delivery state — surface the failure as a warning so an operator
        # can investigate without blocking the user.
        try:
            self._jobs.enqueue(
                SEND_EMAIL_JOB,
                {
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
        except JobError as exc:
            _logger.warning(
                "event=auth.password_reset.email_enqueue_failed user_id=%s reason=%s",
                user.id,
                exc,
            )

        return Ok(
            InternalTokenResult(
                token=raw_token if self._settings.auth_return_internal_tokens else None,
                expires_at=expires_at,
            )
        )


def _reset_url(public_url: str, token: str) -> str:
    return f"{public_url.rstrip('/')}/auth/password/reset?token={token}"
