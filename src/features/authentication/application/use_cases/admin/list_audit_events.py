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
    """Return a page of audit events for admin inspection.

    Pagination is keyset-based on ``(created_at, id)`` because the
    audit-event ``id`` is a UUID rather than a monotonic bigserial — the
    composite tuple is what gives the cursor a stable total ordering.
    The HTTP layer encodes the cursor as base64.
    """

    _repository: AuthRepositoryPort

    def execute(
        self,
        *,
        user_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        before: tuple[datetime, UUID] | None = None,
        limit: int = 100,
    ) -> Result[list[AuditEvent], AuthError]:
        bounded_limit = max(1, min(limit, 500))
        return Ok(
            self._repository.list_audit_events(
                user_id=user_id,
                event_type=event_type,
                since=since,
                before=before,
                limit=bounded_limit,
            )
        )
