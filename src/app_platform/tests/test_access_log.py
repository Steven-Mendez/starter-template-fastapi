"""Access-log middleware coverage for task 6.6.

The access log line MUST carry the same ``request_id`` that the
``X-Request-ID`` response header advertises. Before this change the
line was emitted by uvicorn's built-in access logger, which runs
OUTSIDE the :class:`RequestContextMiddleware` contextvar window and
therefore always reported ``request_id=null``. The platform now
emits the line from :class:`AccessLogMiddleware` mounted inside
:class:`RequestContextMiddleware`.

The test drives a minimal FastAPI app (not the wired-up auth app)
because the only behaviour under test is the access-log middleware
itself: request id stamping happens at the platform layer, not at
the feature layer. A standalone ``/me`` route returning ``200`` is
enough.
"""

from __future__ import annotations

import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


def _app_with_me(settings: AppSettings) -> FastAPI:
    app = build_fastapi_app(settings)

    @app.get("/me")
    def _me() -> dict[str, str]:
        return {"id": "stub"}

    return app


def test_access_log_request_id_matches_response_header(
    test_settings: AppSettings, caplog: pytest.LogCaptureFixture
) -> None:
    """6.6: ``request_id`` in the access record matches ``X-Request-ID``.

    Asserts the line is emitted on the ``api.access`` logger, that
    the ``request_id`` attribute is populated (not ``None``), and
    that it equals the value advertised in the response header.
    """
    caplog.set_level(logging.INFO, logger="api.access")
    with TestClient(_app_with_me(test_settings)) as client:
        response = client.get("/me")

    assert response.status_code == 200
    header_request_id = response.headers["X-Request-ID"]
    assert header_request_id, "X-Request-ID header must be populated"

    records = [r for r in caplog.records if r.name == "api.access"]
    assert records, "expected at least one api.access record for /me"

    me_records = [r for r in records if getattr(r, "path", None) == "/me"]
    assert me_records, "expected an access record carrying path=/me"
    record = me_records[-1]

    record_request_id = getattr(record, "request_id", None)
    assert record_request_id, "access log record_request_id must be non-empty"
    assert record_request_id == header_request_id
    assert getattr(record, "status_code", None) == 200
    assert getattr(record, "method", None) == "GET"


def test_access_log_request_id_matches_client_supplied_header(
    test_settings: AppSettings, caplog: pytest.LogCaptureFixture
) -> None:
    """A client-supplied (valid) ``X-Request-ID`` flows through to the log line.

    Strengthens 6.6: not just "non-empty" — the access log must
    correlate with the value the client (or upstream proxy) chose.
    """
    caplog.set_level(logging.INFO, logger="api.access")
    supplied = "client-supplied-id-abc123"
    with TestClient(_app_with_me(test_settings)) as client:
        response = client.get("/me", headers={"X-Request-ID": supplied})

    assert response.headers["X-Request-ID"] == supplied
    me_records = [
        r
        for r in caplog.records
        if r.name == "api.access" and getattr(r, "path", None) == "/me"
    ]
    assert me_records
    assert getattr(me_records[-1], "request_id", None) == supplied
