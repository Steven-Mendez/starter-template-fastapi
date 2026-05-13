"""SQLModel auth persistence adapter."""

from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)

__all__ = ["SQLModelAuthRepository"]
