from __future__ import annotations

import pytest

from src.platform.config.settings import AppSettings


@pytest.fixture
def test_settings() -> AppSettings:
    """Default deterministic settings for tests."""
    return AppSettings(
        environment="test",
        enable_docs=True,
        cors_origins=["*"],
        trusted_hosts=["*"],
        log_level="WARNING",
        postgresql_dsn="postgresql+psycopg://test:test@localhost:5432/kanban_test",
        health_persistence_backend="postgresql",
        write_api_key=None,
        # Explicitly null out the Redis URL so tests never require a running
        # Redis instance (the .env file may configure one for local dev).
        auth_redis_url=None,
    )
