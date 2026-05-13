from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app_platform.config.settings import AppSettings
from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.crypto import (
    generate_opaque_token,
    hash_token,
)
from features.authentication.application.errors import AuthError, NotFoundError
from features.authentication.application.ports.outbound.auth_repository import (
    TokenRepositoryPort,
)
from features.authentication.application.types import InternalTokenResult
from features.authentication.email_templates import VERIFY_EMAIL_TEMPLATE
from features.email.composition.jobs import SEND_EMAIL_JOB
from features.users.application.ports.user_port import UserPort

_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RequestEmailVerification:
    """Create an email-verification token for an authenticated user.

    Token, audit event, and the ``send_email`` outbox row commit
    atomically inside a single transaction. The relay running in the
    worker dispatches the email through ``JobQueuePort`` once the
    transaction commits.
    """

    _users: UserPort
    _repository: TokenRepositoryPort
    _settings: AppSettings

    def execute(
        self,
        *,
        user_id: UUID,
        ip_address: str | None = None,
    ) -> Result[InternalTokenResult, AuthError]:
        user = self._users.get_by_id(user_id)
        if user is None:
            return Err(NotFoundError("User not found"))

        raw_token = generate_opaque_token()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=self._settings.auth_email_verify_token_expire_minutes
        )
        with self._repository.issue_internal_token_transaction() as tx:
            tx.create_internal_token(
                user_id=user.id,
                purpose="email_verify",
                token_hash=hash_token(raw_token),
                expires_at=expires_at,
                created_ip=ip_address,
            )
            tx.record_audit_event(
                event_type="auth.email_verify_requested",
                user_id=user.id,
                ip_address=ip_address,
            )
            tx.outbox.enqueue(
                job_name=SEND_EMAIL_JOB,
                payload={
                    "to": user.email,
                    "template_name": VERIFY_EMAIL_TEMPLATE,
                    "context": {
                        "app_name": self._settings.app_display_name,
                        "email": user.email,
                        "verify_url": _verify_url(
                            self._settings.app_public_url, raw_token
                        ),
                        "expires_in_minutes": (
                            self._settings.auth_email_verify_token_expire_minutes
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


def _verify_url(public_url: str, token: str) -> str:
    return f"{public_url.rstrip('/')}/auth/email/verify?token={token}"
