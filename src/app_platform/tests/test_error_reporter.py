"""Unit tests for the error-reporting seam.

Covers the three reporter-selection branches and the unhandled-exception
contract: the wired reporter receives every 500 with the full context
shape, and mapped 4xx responses skip the reporter entirely. A fourth set
asserts that a reporter whose ``capture`` raises does not double-fault
the request.
"""

from __future__ import annotations

import builtins
import importlib
import logging
import sys
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.config.settings import AppSettings
from app_platform.observability.error_reporter import (
    ErrorReporterPort,
    LoggingErrorReporter,
    SentryErrorReporter,
)

pytestmark = pytest.mark.unit


class _FakeReporter:
    """Records every ``capture`` call for assertions."""

    def __init__(self) -> None:
        self.calls: list[tuple[BaseException, dict[str, Any]]] = []

    def capture(self, exc: BaseException, **context: Any) -> None:
        self.calls.append((exc, dict(context)))


class _RaisingReporter:
    """Reporter that raises inside ``capture`` — must not escalate."""

    def __init__(self) -> None:
        self.attempts = 0

    def capture(self, exc: BaseException, **context: Any) -> None:
        del exc, context  # unused; this reporter always raises
        self.attempts += 1
        raise RuntimeError("reporter blew up")


def _settings(**overrides: Any) -> AppSettings:
    base: dict[str, Any] = {
        "environment": "test",
        "auth_jwt_secret_key": "test-secret-key-with-at-least-32-bytes",
        "auth_redis_url": None,
    }
    base.update(overrides)
    return AppSettings(**base)


def _make_app_with_fake_reporter() -> tuple[FastAPI, _FakeReporter]:
    """Build a test app with a fake reporter and a boom route."""
    app = build_fastapi_app(_settings(app_sentry_dsn=None))
    fake = _FakeReporter()
    app.state.error_reporter = fake

    @app.get("/__boom")
    def boom() -> None:
        raise RuntimeError("test boom")

    @app.get("/__ok")
    def ok() -> dict[str, str]:
        return {"status": "ok"}

    return app, fake


def _block_sentry_sdk_import(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``import sentry_sdk`` raise ModuleNotFoundError."""
    real_import = builtins.__import__

    def _blocked_import(
        name: str,
        globals_: Any = None,
        locals_: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name == "sentry_sdk":
            raise ModuleNotFoundError("No module named 'sentry_sdk'")
        return real_import(name, globals_, locals_, fromlist, level)

    monkeypatch.delitem(sys.modules, "sentry_sdk", raising=False)
    monkeypatch.setattr(builtins, "__import__", _blocked_import)


# ---------------------------------------------------------------------------
# Reporter selection at startup
# ---------------------------------------------------------------------------


def test_logging_reporter_is_default_when_dsn_unset(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No DSN → LoggingErrorReporter wired + INFO log naming the reporter."""
    with caplog.at_level(logging.INFO, logger="api.error.reporter"):
        app = build_fastapi_app(_settings(app_sentry_dsn=None))

    assert isinstance(app.state.error_reporter, LoggingErrorReporter)
    assert any(
        "error_reporter.selected" in record.getMessage()
        and "reporter=logging" in record.getMessage()
        for record in caplog.records
    )


def test_dsn_set_but_sentry_sdk_missing_falls_back_to_logging(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSN set + sentry_sdk un-importable → LoggingErrorReporter + WARN log."""
    _block_sentry_sdk_import(monkeypatch)

    with caplog.at_level(logging.WARNING, logger="api.error.reporter"):
        app = build_fastapi_app(_settings(app_sentry_dsn="https://example/123"))

    assert isinstance(app.state.error_reporter, LoggingErrorReporter)
    warn_records = [
        r
        for r in caplog.records
        if "error_reporter.fallback" in r.getMessage()
        and "sentry_sdk_not_installed" in r.getMessage()
    ]
    assert warn_records, "expected a WARN line naming the missing extra"
    assert any("pip install" in r.getMessage() for r in warn_records)


def test_dsn_set_and_sentry_sdk_importable_uses_sentry(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DSN set + sentry_sdk importable → SentryErrorReporter + init called."""
    init_calls: list[dict[str, Any]] = []
    set_context_calls: list[tuple[str, dict[str, Any]]] = []
    capture_calls: list[BaseException] = []

    def _fake_init(**kwargs: Any) -> None:
        init_calls.append(kwargs)

    def _fake_set_context(name: str, ctx: dict[str, Any]) -> None:
        set_context_calls.append((name, ctx))

    def _fake_capture_exception(exc: BaseException) -> None:
        capture_calls.append(exc)

    fake_sentry = type(sys)("sentry_sdk")
    fake_sentry.init = _fake_init  # type: ignore[attr-defined]
    fake_sentry.set_context = _fake_set_context  # type: ignore[attr-defined]
    fake_sentry.capture_exception = _fake_capture_exception  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)

    with caplog.at_level(logging.INFO, logger="api.error.reporter"):
        app = build_fastapi_app(
            _settings(
                app_sentry_dsn="https://public@sentry.example/42",
                app_sentry_environment="staging",
                app_sentry_release="abc123",
                otel_traces_sampler_ratio=0.5,
            )
        )

    assert isinstance(app.state.error_reporter, SentryErrorReporter)
    assert len(init_calls) == 1
    init_kwargs = init_calls[0]
    assert init_kwargs["dsn"] == "https://public@sentry.example/42"
    assert init_kwargs["environment"] == "staging"
    assert init_kwargs["release"] == "abc123"
    assert init_kwargs["traces_sample_rate"] == 0.5
    assert any(
        "error_reporter.selected" in r.getMessage()
        and "reporter=sentry" in r.getMessage()
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Unhandled-exception routing
# ---------------------------------------------------------------------------


def test_unhandled_exception_routes_through_reporter() -> None:
    """A 500 path invokes capture exactly once with full context."""
    app, fake = _make_app_with_fake_reporter()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/__boom", headers={"X-Request-ID": "req-test-1"})

    assert resp.status_code == 500
    assert len(fake.calls) == 1
    exc, context = fake.calls[0]
    assert isinstance(exc, RuntimeError)
    assert str(exc) == "test boom"
    assert context["request_id"] == "req-test-1"
    assert context["path"] == "/__boom"
    assert context["method"] == "GET"
    assert context["principal_id"] is None


def test_mapped_4xx_responses_skip_reporter() -> None:
    """A 4xx Problem Details response does NOT page operators."""
    app, fake = _make_app_with_fake_reporter()

    @app.get("/__notfound")
    def notfound() -> None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="missing")

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/__notfound")

    assert resp.status_code == 404
    assert fake.calls == []


def test_reporter_failure_does_not_double_fault_request() -> None:
    """A reporter whose capture raises still yields the original 500."""
    app = build_fastapi_app(_settings(app_sentry_dsn=None))
    raising = _RaisingReporter()
    app.state.error_reporter = raising

    @app.get("/__boom")
    def boom() -> None:
        raise RuntimeError("inner boom")

    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/__boom")

    assert resp.status_code == 500
    assert raising.attempts == 1


# ---------------------------------------------------------------------------
# Adapter behavior in isolation
# ---------------------------------------------------------------------------


def test_logging_reporter_emits_warn_with_extra(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reporter = LoggingErrorReporter()
    exc = ValueError("oops")

    with caplog.at_level(logging.WARNING, logger="api.error.reporter"):
        reporter.capture(
            exc, request_id="r1", path="/x", method="GET", principal_id=None
        )

    matching = [
        r for r in caplog.records if "Unhandled exception captured" in r.getMessage()
    ]
    assert matching, "expected a WARN log line"
    record = matching[0]
    assert record.levelno == logging.WARNING
    assert getattr(record, "error_type", None) == "ValueError"
    assert getattr(record, "request_id", None) == "r1"
    assert getattr(record, "path", None) == "/x"


def test_sentry_reporter_constructor_raises_without_extra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without sentry_sdk on the path, constructing the adapter fails fast."""
    _block_sentry_sdk_import(monkeypatch)

    with pytest.raises(ModuleNotFoundError):
        SentryErrorReporter()


def test_sentry_reporter_capture_forwards_to_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_context_calls: list[tuple[str, dict[str, Any]]] = []
    capture_calls: list[BaseException] = []

    def _set_context(name: str, ctx: dict[str, Any]) -> None:
        set_context_calls.append((name, ctx))

    def _capture_exception(exc: BaseException) -> None:
        capture_calls.append(exc)

    fake_sentry = type(sys)("sentry_sdk")
    fake_sentry.set_context = _set_context  # type: ignore[attr-defined]
    fake_sentry.capture_exception = _capture_exception  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)

    reporter = SentryErrorReporter()
    exc = RuntimeError("boom")
    reporter.capture(exc, request_id="r1", path="/x", method="POST", principal_id="u1")

    assert capture_calls == [exc]
    assert set_context_calls == [
        (
            "request",
            {
                "request_id": "r1",
                "path": "/x",
                "method": "POST",
                "principal_id": "u1",
            },
        )
    ]


def test_sentry_reporter_capture_swallows_sdk_errors(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A broken transport must never re-raise out of ``capture``."""

    def _broken(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("transport failed")

    fake_sentry = type(sys)("sentry_sdk")
    fake_sentry.set_context = _broken  # type: ignore[attr-defined]
    fake_sentry.capture_exception = _broken  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentry_sdk", fake_sentry)

    reporter = SentryErrorReporter()
    with caplog.at_level(logging.ERROR, logger="api.error.reporter"):
        reporter.capture(RuntimeError("inner"))  # MUST NOT raise


# ---------------------------------------------------------------------------
# Protocol shape
# ---------------------------------------------------------------------------


def test_logging_reporter_satisfies_protocol() -> None:
    reporter: ErrorReporterPort = LoggingErrorReporter()
    assert hasattr(reporter, "capture")


def test_error_reporter_module_reimport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reimporting the module is safe — no module-level side effects."""
    monkeypatch.delitem(
        sys.modules, "app_platform.observability.error_reporter", raising=False
    )
    mod = importlib.import_module("app_platform.observability.error_reporter")
    assert hasattr(mod, "ErrorReporterPort")
