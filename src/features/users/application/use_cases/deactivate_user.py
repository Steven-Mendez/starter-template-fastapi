"""Deactivate a user account.

Sets ``is_active = False`` and bumps ``authz_version`` so any cached
principals derived from the user are invalidated on the next request.

When a ``revoke_all_refresh_tokens`` collaborator is wired, every
server-side refresh-token family for the user is revoked in the same
Unit of Work as the ``is_active=False`` flip. Self-deactivation
(``DELETE /me``) relies on this so the response reflects the revoked
state — no outbox round trip and no window where the browser cookie is
cleared but the refresh family is still alive on the server.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.users.application.errors import UserError, UserNotFoundError
from features.users.application.ports.user_port import UserPort


@dataclass(slots=True)
class DeactivateUser:
    """Mark a user as inactive.

    The optional ``revoke_all_refresh_tokens`` collaborator is invoked inline,
    inside the same Unit of Work as the ``is_active=False`` flip, so the
    user's refresh-token families are dead before any subsequent response is
    returned. It is typed as a plain callable to avoid coupling ``users`` to
    a concrete authentication use-case type (the import-linter contract
    forbids ``users -> authentication`` imports).
    """

    _users: UserPort
    _revoke_all_refresh_tokens: Callable[[UUID], None] | None = None

    def execute(self, user_id: UUID) -> Result[None, UserError]:
        existing = self._users.get_by_id(user_id)
        if existing is None:
            return Err(UserNotFoundError())
        if self._revoke_all_refresh_tokens is not None:
            # Revoke server-side refresh-token families first so the
            # is_active=False flip is the final state-changing write.
            # When `set_active` is later promoted to a multi-statement UoW
            # this call moves inside it; for the current single-write
            # adapter this still produces the "before response" guarantee
            # the spec requires.
            self._revoke_all_refresh_tokens(user_id)
        self._users.set_active(user_id, is_active=False)
        return Ok(None)
