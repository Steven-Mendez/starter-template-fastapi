"""Auth-side adapter implementing authorization's ``CredentialVerifierPort``."""

from __future__ import annotations

from features.authentication.adapters.outbound.credential_verifier.sqlmodel import (
    SQLModelCredentialVerifierAdapter,
)

__all__ = ["SQLModelCredentialVerifierAdapter"]
