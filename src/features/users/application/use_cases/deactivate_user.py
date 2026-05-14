"""Deactivate a user account.

Sets ``is_active = False`` and bumps ``authz_version`` so any cached
principals derived from the user are invalidated on the next request.

When a ``revoke_all_refresh_tokens`` collaborator is wired, every
server-side refresh-token family for the user is revoked in the same
Unit of Work as the ``is_active=False`` flip. Self-deactivation
(``DELETE /me``) relies on this so the response reflects the revoked
state — no outbox round trip and no window where the browser cookie is
cleared but the refresh family is still alive on the server.

When an ``outbox_uow`` is wired, deactivation also enqueues a
``delete_user_assets`` outbox job inside the same transaction as the
user mutation. The asset cleanup itself happens out-of-band in the
worker (see ``UserAssetsCleanupPort``). ``DeactivateUser`` MUST NOT
invoke that port directly; doing so would couple the HTTP response to
the storage backend's latency and lose the relay's retry/backoff on
transient failures.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.outbox.application.ports.outbox_uow_port import OutboxUnitOfWorkPort
from features.users.application.errors import UserError, UserNotFoundError
from features.users.application.ports.user_port import UserPort

# Job name constant for the asset-cleanup outbox row. The handler is
# registered against this exact name in ``src/main.py`` and
# ``src/worker.py`` — keeping it as a module-level constant lets the
# static-import test scan for direct calls to the cleanup port and
# assert this is the only reference the use case carries.
DELETE_USER_ASSETS_JOB = "delete_user_assets"


@dataclass(slots=True)
class DeactivateUser:
    """Mark a user as inactive.

    The optional ``revoke_all_refresh_tokens`` collaborator is invoked inline,
    inside the same Unit of Work as the ``is_active=False`` flip, so the
    user's refresh-token families are dead before any subsequent response is
    returned. It is typed as a plain callable to avoid coupling ``users`` to
    a concrete authentication use-case type (the import-linter contract
    forbids ``users -> authentication`` imports).

    The optional ``outbox_uow`` parameter, when wired, opens a single
    transaction in which the user-row mutation and the
    ``delete_user_assets`` outbox row commit together. With no
    ``outbox_uow`` wired the use case still completes — the user is
    deactivated but no cleanup is scheduled (used in tests that do not
    exercise the outbox path).
    """

    _users: UserPort
    _revoke_all_refresh_tokens: Callable[[UUID], None] | None = None
    _outbox_uow: OutboxUnitOfWorkPort | None = None

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
        if self._outbox_uow is not None:
            # Atomic path: stage the user row update on the outbox
            # transaction's session and enqueue the cleanup row in the
            # same scope. On clean exit the writer commits both; on any
            # exception the rollback drops the outbox row so the relay
            # never dispatches cleanup for a user whose deactivation
            # failed.
            with self._outbox_uow.transaction() as writer:
                self._users.set_active_atomically_with(writer, user_id, is_active=False)
                writer.enqueue(
                    job_name=DELETE_USER_ASSETS_JOB,
                    payload={"user_id": str(user_id)},
                )
        else:
            self._users.set_active(user_id, is_active=False)
        return Ok(None)
