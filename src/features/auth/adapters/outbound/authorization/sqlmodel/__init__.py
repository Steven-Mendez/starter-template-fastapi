"""Default in-repo authorization adapter (SQLModel-backed)."""

from src.features.auth.adapters.outbound.authorization.sqlmodel.repository import (
    SessionSQLModelAuthorizationAdapter,
    SQLModelAuthorizationAdapter,
)

__all__ = [
    "SQLModelAuthorizationAdapter",
    "SessionSQLModelAuthorizationAdapter",
]
