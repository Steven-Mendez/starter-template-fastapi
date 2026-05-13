"""Auth-side adapters for the authorization feature's UserAuthzVersionPort."""

from __future__ import annotations

from features.users.adapters.outbound.authz_version.sqlmodel import (
    SessionSQLModelUserAuthzVersionAdapter,
    SQLModelUserAuthzVersionAdapter,
)

__all__ = [
    "SQLModelUserAuthzVersionAdapter",
    "SessionSQLModelUserAuthzVersionAdapter",
]
