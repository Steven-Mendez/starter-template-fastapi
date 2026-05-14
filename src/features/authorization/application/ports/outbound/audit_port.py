"""Port for emitting ``authz.*`` audit events.

Audit events live in the auth feature's ``auth_audit_events`` table.
Authorization writes its own ``authz.*`` events through this port so it
never touches the auth schema directly.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class AuditPort(Protocol):
    """Append-only event sink the auth feature implements."""

    def record(
        self,
        event_type: str,
        *,
        user_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Persist one audit event.

        Implementations SHALL append a row to the auth audit log and
        SHALL NOT raise for valid input. ``event_type`` is a dotted
        namespace (``authz.system_admin_bootstrapped`` etc.).
        """
        ...
