"""Outbound port for reading a user's audit events.

The export endpoint (GDPR Art. 15) needs to include the user's audit
trail in the JSON blob, but the users feature cannot import the
authentication feature's persistence layer (Import Linter forbids
``users ↛ authentication``). This narrow read-only port lets users
ship the export pipeline without learning the audit schema.

Implementations live in the authentication feature and call the
existing ``list_audit_events`` query under the hood. The use case in
users de-serializes the returned dicts straight into JSON; no domain
type is shared.
"""

from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID


class UserAuditReaderPort(Protocol):
    """Return a JSON-serializable view of the user's audit events."""

    def list_for_user(self, user_id: UUID) -> list[dict[str, Any]]:
        """Return every audit event whose ``user_id`` matches.

        The list is bounded by the implementation's query limit; the
        export blob is therefore inherently best-effort for users with
        unusually long histories. Returned dicts MUST be JSON-safe
        (UUIDs and datetimes coerced to strings).
        """
        ...
