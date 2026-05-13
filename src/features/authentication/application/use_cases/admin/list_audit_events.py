from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app_platform.shared.result import Ok, Result
from features.authentication.application.errors import AuthError
from features.authentication.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)
from features.authentication.domain.models import AuditEvent


@dataclass(slots=True)
class ListAuditEvents:
    _repository: AuthRepositoryPort

    def execute(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> Result[list[AuditEvent], AuthError]:
        bounded_limit = max(1, min(limit, 500))
        return Ok(
            self._repository.list_audit_events(
                user_id=user_id,
                event_type=event_type,
                since=since,
                limit=bounded_limit,
            )
        )
