"""Deactivate a user account.

Sets ``is_active = False`` and bumps ``authz_version`` so any cached
principals derived from the user are invalidated on the next request.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from src.features.users.application.errors import UserError
from src.features.users.application.ports.user_port import UserPort
from src.platform.shared.result import Err, Ok, Result


@dataclass(slots=True)
class DeactivateUser:
    """Mark a user as inactive."""

    _users: UserPort

    def execute(self, user_id: UUID) -> Result[None, UserError]:
        existing = self._users.get_by_id(user_id)
        if existing is None:
            return Err(UserError.NOT_FOUND)
        self._users.set_active(user_id, is_active=False)
        return Ok(None)
