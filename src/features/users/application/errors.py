"""Application-layer errors for the users feature."""

from __future__ import annotations

from app_platform.shared.errors import ApplicationError


class UserError(ApplicationError):
    """Base class for user-feature errors returned as ``Err`` values."""


class UserNotFoundError(UserError):
    """Raised when a referenced user does not exist."""


class UserAlreadyExistsError(UserError):
    """Raised when a registration or profile-update conflicts with an existing user."""
