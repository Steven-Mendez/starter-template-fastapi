"""Integration-test fixtures for the authorization feature.

Reuses the auth feature's testcontainer + repository fixtures because
the authorization feature's integration tests need both the
relationships table and a live auth schema (the SQLite/Postgres repo
manages every shared SQLModel table at once).
"""

from __future__ import annotations

from src.features.authentication.tests.integration.conftest import (  # noqa: F401
    _auth_postgres_url,
    postgres_auth_repository,
    sqlite_auth_repository,
)
