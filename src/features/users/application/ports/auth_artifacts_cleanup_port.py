"""Outbound port for scrubbing authentication-owned PII during user erasure.

The users feature owns the GDPR-Art.17 ``EraseUser`` orchestration but
cannot reach into the authentication feature's tables directly
(``users ↛ authentication`` is an Import Linter contract). This port
exposes the three writes the spec mandates as session-scoped methods
that stage their work on the active transaction's writer:

* ``scrub_audit_events`` — strip ``ip_address``/``user_agent``/``family_id``
  keys from every ``auth_audit_events.event_metadata`` JSONB row for the
  user, and null the dedicated columns. The rows themselves survive so
  the audit trail's referential integrity is preserved.
* ``delete_credentials_and_tokens`` — delete every ``credentials``,
  ``refresh_tokens``, and ``auth_internal_tokens`` row for the user.
  Credential material does not survive erasure.
* ``record_user_erased_event`` — append a final ``user.erased`` audit
  event whose payload contains only ``{user_id, reason}``. No email,
  no IP — the event itself MUST NOT reintroduce PII.

Implementations are wired in the authentication feature's composition
root and SHALL be idempotent on a user that is already erased.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class AuthArtifactsCleanupPort(Protocol):
    """Session-scoped scrub/delete of authentication-owned PII."""

    def scrub_audit_events(self, writer: object, user_id: UUID) -> None:
        """Strip PII keys from ``auth_audit_events`` rows for ``user_id``.

        Implementations stage the ``UPDATE`` on ``writer``'s underlying
        transaction (matching the :class:`OutboxWriter` Protocol used
        elsewhere in the codebase). The transaction commits or rolls
        back as a single unit with the user-row scrub.
        """
        ...

    def delete_credentials_and_tokens(self, writer: object, user_id: UUID) -> None:
        """Delete every credential / refresh-token / internal-token row.

        All three deletes run inside the same transaction as
        :meth:`scrub_audit_events`.
        """
        ...

    def record_user_erased_event(
        self,
        writer: object,
        user_id: UUID,
        reason: str,
    ) -> None:
        """Append a ``user.erased`` row with payload ``{user_id, reason}``.

        Payload MUST NOT contain email, IP, or user-agent — those would
        defeat the point of erasure. The row commits with the rest of
        the erasure transaction.
        """
        ...
