"""Default in-repo authorization adapter (SQLModel-backed)."""

from features.authorization.adapters.outbound.sqlmodel.adapter import (
    SessionSQLModelAuthorizationAdapter,
    SQLModelAuthorizationAdapter,
)

__all__ = [
    "SQLModelAuthorizationAdapter",
    "SessionSQLModelAuthorizationAdapter",
]
