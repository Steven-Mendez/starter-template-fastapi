"""SQLModel auth persistence adapter."""

from src.features.auth.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelAuthRepository,
)

__all__ = ["SQLModelAuthRepository"]
