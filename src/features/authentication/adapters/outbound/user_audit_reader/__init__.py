"""Authentication adapter implementing the users feature's :class:`UserAuditReaderPort`.

Exposes the user's audit-event history as a list of JSON-safe dicts so
the users-feature export endpoint can include it in the data-subject-
access response. Read-only — the adapter neither writes nor mutates
audit rows.
"""

from __future__ import annotations

from features.authentication.adapters.outbound.user_audit_reader.sqlmodel import (
    SQLModelUserAuditReaderAdapter,
)

__all__ = ["SQLModelUserAuditReaderAdapter"]
