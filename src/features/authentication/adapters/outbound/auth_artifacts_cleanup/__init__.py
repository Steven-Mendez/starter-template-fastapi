"""Auth implementation of :class:`AuthArtifactsCleanupPort` for users.

Lets the users-feature ``EraseUser`` use case stage authentication-owned
PII scrubs inside its outer transaction without importing the auth
schema directly (forbidden by the ``users ↛ authentication`` Import
Linter contract). See the port docstring for the GDPR rationale.
"""

from __future__ import annotations

from features.authentication.adapters.outbound.auth_artifacts_cleanup.sqlmodel import (
    SQLModelAuthArtifactsCleanupAdapter,
)

__all__ = ["SQLModelAuthArtifactsCleanupAdapter"]
