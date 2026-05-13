"""Update the authenticated user's profile.

The current ``User`` shape exposes only ``email`` as a mutable profile
field. The use case is intentionally narrow: identity-shaped writes
(activation status, verification, password) flow through dedicated use
cases so the audit story stays simple.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.users.application.errors import UserError, UserNotFoundError
from features.users.application.ports.user_port import UserPort
from features.users.domain.user import User


@dataclass(slots=True)
class UpdateProfile:
    """Replace the user's mutable profile fields."""

    _users: UserPort

    def execute(
        self,
        *,
        user_id: UUID,
        email: str | None = None,
    ) -> Result[User, UserError]:
        existing = self._users.get_by_id(user_id)
        if existing is None:
            return Err(UserNotFoundError())
        if email is None:
            return Ok(existing)
        normalized = email.strip().lower()
        if normalized == existing.email:
            return Ok(existing)
        return self._users.update_email(user_id, normalized)
