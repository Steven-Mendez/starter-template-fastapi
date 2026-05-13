"""Auth-side adapter for the authorization feature's AuditPort."""

from __future__ import annotations

from features.authentication.adapters.outbound.audit.sqlmodel import (
    SQLModelAuditAdapter,
)

__all__ = ["SQLModelAuditAdapter"]
