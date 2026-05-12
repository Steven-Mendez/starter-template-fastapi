"""Auth-side adapter for the users feature's CredentialWriterPort."""

from __future__ import annotations

from src.features.authentication.adapters.outbound.credential_writer.sqlmodel import (
    SQLModelCredentialWriterAdapter,
)

__all__ = ["SQLModelCredentialWriterAdapter"]
