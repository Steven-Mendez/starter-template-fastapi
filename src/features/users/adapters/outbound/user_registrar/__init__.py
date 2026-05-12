"""Auth-side adapter for the authorization feature's UserRegistrarPort."""

from __future__ import annotations

from src.features.users.adapters.outbound.user_registrar.sqlmodel import (
    SQLModelUserRegistrarAdapter,
)

__all__ = ["SQLModelUserRegistrarAdapter"]
