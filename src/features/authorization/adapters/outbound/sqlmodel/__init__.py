"""Default in-repo authorization adapter (SQLModel-backed)."""

from src.features.authorization.adapters.outbound.sqlmodel.repository import (
    SessionSQLModelAuthorizationAdapter,
    SQLModelAuthorizationAdapter,
)

__all__ = [
    "SQLModelAuthorizationAdapter",
    "SessionSQLModelAuthorizationAdapter",
]
