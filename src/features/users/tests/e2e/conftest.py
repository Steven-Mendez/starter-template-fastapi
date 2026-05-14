"""Pytest fixtures for users-feature e2e tests.

Reuses the fully wired FastAPI app from the authentication e2e fixtures so
``/me`` flows are exercised against the same composition root (auth +
authorization + users) the production app uses. Self-deactivation in
particular must run through the wired refresh-token revoker, which is
attached to the users container only when both halves of the composition
exist.
"""

from __future__ import annotations

# Re-export the auth e2e fixtures (``auth_context``, ``client``, etc.) so
# users tests can request them by name without redefining the wiring.
from features.authentication.tests.e2e.conftest import (  # noqa: F401
    AuthTestContext,
    auth_context,
    auth_repository,
    client,
)
