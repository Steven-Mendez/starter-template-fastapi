"""Port for verifying a user's stored credential against a candidate password.

Used by ``BootstrapSystemAdmin`` to gate the explicit-opt-in promotion
of a pre-existing user: the operator must supply that user's actual
password, which is checked against the persisted credential row.

The port is owned by the authorization feature and implemented by
authentication (the credential row lives in the auth schema). It is
intentionally narrow: a single read-side check with no side effects
(no audit events, no rate-limit counters), so call sites at system
startup do not pollute the auth observability surface.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app_platform.shared.result import Result
from features.authorization.application.errors import CredentialVerificationError


class CredentialVerifierPort(Protocol):
    """Stateless ``(user_id, password)`` verifier."""

    def verify(
        self, user_id: UUID, password: str
    ) -> Result[None, CredentialVerificationError]:
        """Return ``Ok(None)`` iff ``password`` matches the stored credential.

        Implementations SHALL be free of side effects: no audit events,
        no rate-limit counter increments, no cache writes. The port
        exists specifically to support system-startup flows where those
        side effects are inappropriate.
        """
        ...
