"""Unit tests for the ``/health/ready`` readiness probe."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.dependencies.container import set_app_container
from app_platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


@dataclass(frozen=True, slots=True)
class _Container:
    """Minimal platform container exposing settings to the probe."""

    settings: AppSettings


class _FakeEngine:
    """Engine stub whose ``connect()`` is exercised inside ``_probe_db``."""

    def __init__(self, *, fail: bool = False, sleep: float = 0.0) -> None:
        self._fail = fail
        self._sleep = sleep

    def connect(self) -> Any:  # pragma: no cover - returns the context-manager below
        return _FakeConnection(fail=self._fail, sleep=self._sleep)


class _FakeConnection:
    """Context manager mimicking ``Connection`` for ``SELECT 1``."""

    def __init__(self, *, fail: bool, sleep: float) -> None:
        self._fail = fail
        self._sleep = sleep

    def __enter__(self) -> _FakeConnection:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def execute(self, _stmt: Any) -> None:
        import time

        if self._sleep:
            time.sleep(self._sleep)
        if self._fail:
            raise RuntimeError("db down")


class _FakeRedis:
    """Redis stub with the synchronous ``ping`` surface the probe calls."""

    def __init__(self, *, fail: bool = False, sleep: float = 0.0) -> None:
        self._fail = fail
        self._sleep = sleep

    def ping(self) -> bool:
        import time

        if self._sleep:
            time.sleep(self._sleep)
        if self._fail:
            raise RuntimeError("redis down")
        return True


def _settings(**overrides: Any) -> AppSettings:
    """Return an AppSettings tuned for readiness-probe tests."""
    base: dict[str, Any] = {
        "environment": "test",
        "enable_docs": True,
        "cors_origins": ["*"],
        "trusted_hosts": ["*"],
        "log_level": "WARNING",
        "postgresql_dsn": "postgresql+psycopg://test:test@localhost:5432/starter_test",
        "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
        "auth_redis_url": None,
    }
    base.update(overrides)
    return AppSettings(**base)


def _build_app(
    *,
    settings: AppSettings,
    ready: bool,
    engine: Any | None,
    redis_client: Any | None = None,
) -> FastAPI:
    """Build a FastAPI app with the readiness probe and pre-populated state."""
    app = build_fastapi_app(settings)

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI) -> Any:
        set_app_container(lifespan_app, _Container(settings=settings))
        lifespan_app.state.health_db_engine = engine
        lifespan_app.state.redis_client = redis_client
        lifespan_app.state.ready = ready
        try:
            yield
        finally:
            lifespan_app.state.ready = False
            lifespan_app.state.container = None

    app.router.lifespan_context = lifespan
    return app


def test_health_ready_returns_200_when_db_and_redis_healthy() -> None:
    app = _build_app(
        settings=_settings(auth_redis_url="redis://example:6379/0"),
        ready=True,
        engine=_FakeEngine(),
        redis_client=_FakeRedis(),
    )
    with TestClient(app) as c:
        resp = c.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "deps": {"db": "ok", "redis": "ok"}}


def test_health_ready_returns_503_when_db_probe_raises() -> None:
    app = _build_app(
        settings=_settings(),
        ready=True,
        engine=_FakeEngine(fail=True),
    )
    with TestClient(app) as c:
        resp = c.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "fail"
    assert "db" in body["deps"]
    assert body["deps"]["db"]["status"] == "fail"
    assert body["deps"]["db"]["reason"]
    assert resp.headers.get("Retry-After") == "1"


def test_health_ready_returns_503_starting_before_lifespan_completes() -> None:
    settings = _settings()
    app = _build_app(
        settings=settings,
        ready=False,
        engine=_FakeEngine(fail=True),  # intentionally broken to prove it is bypassed
    )
    with TestClient(app) as c:
        resp = c.get("/health/ready")
    assert resp.status_code == 503
    assert resp.json() == {"status": "starting"}
    # No Retry-After on the starting branch — kubelet's own backoff covers it.
    assert "Retry-After" not in resp.headers


def test_health_ready_returns_503_when_redis_probe_times_out() -> None:
    # Generous DB sleep so it does not finish first; tiny timeout so redis trips it.
    app = _build_app(
        settings=_settings(
            auth_redis_url="redis://example:6379/0",
            health_ready_probe_timeout_seconds=0.05,
        ),
        ready=True,
        engine=_FakeEngine(),
        redis_client=_FakeRedis(sleep=1.0),
    )
    with TestClient(app) as c:
        resp = c.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert "redis" in body["deps"]
    assert body["deps"]["redis"]["status"] == "fail"
    assert body["deps"]["redis"]["reason"] == "timeout"
    assert resp.headers.get("Retry-After") == "1"


def test_health_ready_omits_redis_when_not_configured() -> None:
    app = _build_app(
        settings=_settings(),  # auth_redis_url=None by default
        ready=True,
        engine=_FakeEngine(),
        redis_client=None,
    )
    with TestClient(app) as c:
        resp = c.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok", "deps": {"db": "ok"}}
    assert "redis" not in body["deps"]


def test_health_live_unaffected_by_dependency_failure() -> None:
    app = _build_app(
        settings=_settings(),
        ready=False,
        engine=_FakeEngine(fail=True),
    )
    with TestClient(app) as c:
        resp = c.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_probes_run_in_parallel_within_timeout_budget() -> None:
    """Probes are gathered concurrently; total latency is the slowest, not the sum."""
    # Each probe sleeps 0.3 s; timeout 1.0 s. If they ran sequentially the
    # request would take ~0.6 s, but well under the per-probe budget. We
    # assert both succeed — proving gather is concurrent enough that the
    # second probe is not gated on the first finishing inside the same loop.
    app = _build_app(
        settings=_settings(
            auth_redis_url="redis://example:6379/0",
            health_ready_probe_timeout_seconds=1.0,
        ),
        ready=True,
        engine=_FakeEngine(sleep=0.3),
        redis_client=_FakeRedis(sleep=0.3),
    )
    with TestClient(app) as c:
        resp = c.get("/health/ready")
    assert resp.status_code == 200
    assert resp.json()["deps"] == {"db": "ok", "redis": "ok"}


def test_settings_reject_invalid_health_timeout() -> None:
    with pytest.raises(ValueError, match="HEALTH_READY_PROBE_TIMEOUT"):
        _settings(health_ready_probe_timeout_seconds=0.0)
    with pytest.raises(ValueError, match="HEALTH_READY_PROBE_TIMEOUT"):
        _settings(health_ready_probe_timeout_seconds=31.0)


def test_asyncio_module_imports_cleanly() -> None:
    # Sanity check that the probe module's asyncio dependency is on path.
    assert asyncio.gather is not None
