"""SQLModel-backed :class:`UserAuditReaderPort` implementation.

Delegates to the existing ``AuditRepositoryPort.list_audit_events`` and
flattens the domain dataclass into a JSON-safe dict so the export blob
can be written verbatim to the file-storage backend without further
serialization plumbing inside the users feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from features.authentication.application.ports.outbound.auth_repository import (
    AuditRepositoryPort,
)

# Cap on the number of audit events included in a single export. The
# limit matches the upper bound enforced by ``ListAuditEvents`` so the
# export shape stays predictable for unusually busy users.
_DEFAULT_EXPORT_LIMIT = 500


@dataclass(slots=True)
class SQLModelUserAuditReaderAdapter:
    """Return the user's audit events as JSON-safe dicts."""

    repository: AuditRepositoryPort

    def list_for_user(self, user_id: UUID) -> list[dict[str, Any]]:
        events = self.repository.list_audit_events(
            user_id=user_id, limit=_DEFAULT_EXPORT_LIMIT
        )
        return [_to_jsonable(e) for e in events]


def _to_jsonable(event: Any) -> dict[str, Any]:
    """Coerce an ``AuditEvent`` dataclass into JSON-safe primitives."""
    return {
        "id": str(event.id) if event.id is not None else None,
        "user_id": str(event.user_id) if event.user_id is not None else None,
        "event_type": event.event_type,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "metadata": dict(event.metadata) if event.metadata else {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }
