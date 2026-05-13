"""SQLModel auth persistence adapter."""

from features.authentication.adapters.outbound.persistence.sqlmodel.repository import (  # noqa: E501
    SQLModelAuthRepository,
)

__all__ = ["SQLModelAuthRepository"]
