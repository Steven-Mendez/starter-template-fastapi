"""Audit-log adapter the authorization feature uses for ``authz.*`` events.

Wraps the existing ``record_audit_event`` repository method so the
``auth_audit_events`` table accepts cross-feature events without the
authorization feature ever importing the auth schema.
"""

from __future__ import annotations

from uuid import UUID

from src.features.auth.application.ports.outbound.auth_repository import (
    AuthRepositoryPort,
)


class SQLModelAuditAdapter:
    """Append-only adapter; one method, one row per call."""

    def __init__(self, repository: AuthRepositoryPort) -> None:
        self._repository = repository

    def record(
        self,
        event_type: str,
        *,
        user_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self._repository.record_audit_event(
            event_type=event_type,
            user_id=user_id,
            metadata=metadata,
        )
