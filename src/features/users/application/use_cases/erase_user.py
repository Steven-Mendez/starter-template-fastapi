"""GDPR Art. 17 erasure: scrub user PII in one transaction.

The use case is the orchestration core of the data-subject-rights
pipeline. Triggered from two routes (``DELETE /me/erase`` for self-
service, ``POST /admin/users/{user_id}/erase`` for admin paths), and
dispatched asynchronously via the ``erase_user`` background job
handler so the HTTP response returns ``202 Accepted`` immediately.

Inside a single :class:`OutboxUnitOfWorkPort` transaction the use case:

1. Scrubs the ``users`` row (``email`` → placeholder, ``last_login_at``
   → NULL, ``is_active=false``, ``is_erased=true``, ``authz_version``
   bumped).
2. Scrubs ``auth_audit_events`` for the user — the rows survive
   (referential integrity, audit-trail count parity) but their PII
   columns and JSONB keys are cleared.
3. Deletes ``credentials``, ``refresh_tokens``, and
   ``auth_internal_tokens`` rows for the user.
4. Records a final ``user.erased`` audit event with payload
   ``{user_id, reason}`` — no email, no IP.
5. Enqueues a ``delete_user_assets`` outbox row so the worker walks the
   per-user blob prefix on the wired :class:`FileStoragePort`. The
   storage cleanup runs out of band; the user-facing erasure is
   considered complete once the transaction commits.

The use case is idempotent on a row that is already erased: every
inner step short-circuits and the transaction commits cleanly.

The cross-feature scrub of authentication tables is mediated by
:class:`AuthArtifactsCleanupPort` so this use case stays free of the
auth schema (the ``users ↛ authentication`` Import Linter contract).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.outbox.application.ports.outbox_uow_port import OutboxUnitOfWorkPort
from features.users.application.errors import UserError, UserNotFoundError
from features.users.application.ports.auth_artifacts_cleanup_port import (
    AuthArtifactsCleanupPort,
)
from features.users.application.ports.user_port import UserPort

# Job name constants — must match the registrations in ``src/main.py``
# and ``src/worker.py``. Pulled into module-level constants so the
# static-import test can scan for inline string usage.
DELETE_USER_ASSETS_JOB = "delete_user_assets"

ErasureReason = Literal["self_request", "admin_request"]


@dataclass(slots=True)
class EraseUser:
    """Run the GDPR Art. 17 scrub for a user inside a single transaction.

    All three collaborators are required for the production wiring; the
    use case has no "no-outbox" branch because erasure without an outbox
    row would leak storage blobs for the lifetime of the prefix. Unit
    tests that don't exercise the full pipeline construct fakes that
    satisfy the ports without round-tripping through a queue.
    """

    _users: UserPort
    _auth_artifacts: AuthArtifactsCleanupPort
    _outbox_uow: OutboxUnitOfWorkPort

    def execute(
        self,
        user_id: UUID,
        reason: ErasureReason = "self_request",
    ) -> Result[None, UserError]:
        # Use the raw read so an already-erased row still surfaces here
        # — that makes the idempotent re-run path explicit rather than
        # collapsing into "user not found".
        existing = self._users.get_raw_by_id(user_id)
        if existing is None:
            return Err(UserNotFoundError())
        if existing.is_erased:
            # Already erased — every inner step is a no-op, but we
            # also avoid enqueuing a duplicate cleanup job since the
            # original erasure already enqueued one (or the cleanup
            # already drained).
            return Ok(None)
        with self._outbox_uow.transaction() as writer:
            # Order matters: scrub authentication artifacts first so a
            # mid-transaction failure leaves nothing pointing at the
            # not-yet-scrubbed user row.
            self._auth_artifacts.scrub_audit_events(writer, user_id)
            self._auth_artifacts.delete_credentials_and_tokens(writer, user_id)
            self._users.scrub_for_erasure_atomically_with(writer, user_id)
            self._auth_artifacts.record_user_erased_event(writer, user_id, reason)
            writer.enqueue(
                job_name=DELETE_USER_ASSETS_JOB,
                payload={"user_id": str(user_id)},
            )
        return Ok(None)
