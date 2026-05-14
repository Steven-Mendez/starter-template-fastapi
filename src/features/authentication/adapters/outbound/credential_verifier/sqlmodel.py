"""Adapter implementing authorization's :class:`CredentialVerifierPort`.

Reads the user's ``credentials`` row via the existing
:class:`CredentialRepositoryPort` and compares the supplied plaintext
password against the stored Argon2id hash with the auth feature's
:class:`PasswordService`. The adapter is deliberately side-effect-free:
no audit events, no rate-limit counter increments, no cache writes —
``BootstrapSystemAdmin`` (its sole caller today) runs at process
startup and would otherwise pollute those observability surfaces.

A missing credential row maps to the same
:class:`CredentialVerificationError` as a wrong password: at the call
site they reduce to "operator did not supply the correct password for
this user", and surfacing the distinction would let an attacker probe
account existence through bootstrap re-runs.

The import from ``features.authorization.application.errors`` is the
port-implementation edge: ``CredentialVerifierPort`` is owned by
authorization and the adapter must return that error type so the
authorization-side use case can match it exhaustively. The Import
Linter contract carries an explicit ignore for this single edge.
"""

from __future__ import annotations

from uuid import UUID

from app_platform.shared.result import Err, Ok, Result
from features.authentication.application.crypto import PasswordService
from features.authentication.application.ports.outbound.auth_repository import (
    CredentialRepositoryPort,
)
from features.authorization.application.errors import CredentialVerificationError


class SQLModelCredentialVerifierAdapter:
    """Loads the credential row and runs ``PasswordService.verify_password``."""

    def __init__(
        self,
        *,
        credentials: CredentialRepositoryPort,
        password_service: PasswordService,
    ) -> None:
        self._credentials = credentials
        self._password_service = password_service

    def verify(
        self, user_id: UUID, password: str
    ) -> Result[None, CredentialVerificationError]:
        credential = self._credentials.get_credential_for_user(user_id)
        if credential is None:
            return Err(CredentialVerificationError(user_id))
        if not self._password_service.verify_password(credential.hash, password):
            return Err(CredentialVerificationError(user_id))
        return Ok(None)
