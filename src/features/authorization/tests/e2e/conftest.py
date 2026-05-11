"""E2e fixtures for authorization tests.

Reuses the auth feature's e2e harness (which already wires the
authorization container) because the bootstrap flow exercises both
features end-to-end. Tests that need fakes instead of the live engine
should construct their own application.
"""

from __future__ import annotations

from src.features.auth.tests.e2e.conftest import (  # noqa: F401
    AuthTestContext,
    auth_context,
    auth_repository,
)
