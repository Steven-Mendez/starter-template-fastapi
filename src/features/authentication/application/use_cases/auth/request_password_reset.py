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
    TokenRepositoryPort,
)
from src.features.authentication.application.types import InternalTokenResult
from src.features.authentication.email_templates import PASSWORD_RESET_TEMPLATE
from src.features.email.composition.jobs import SEND_EMAIL_JOB
from src.features.users.application.ports.user_port import UserPort
from src.platform.config.settings import AppSettings
from src.platform.shared.result import Ok, Result

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
        with self._repository.issue_internal_token_transaction() as tx:
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
