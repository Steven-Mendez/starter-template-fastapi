"""Unit tests for ``_enforce_cookie_origin`` covering header combinations.

The CSRF-style cookie-origin check is the second line of defence behind
SameSite for the refresh cookie. It must:

* accept a present-and-trusted ``Origin`` header,
* fall back to ``Referer`` when ``Origin`` is absent,
* reject the request when both are absent **only** if the refresh
  cookie is on the request (no signal of provenance to validate),
* stay a no-op when no refresh cookie is present (backwards compat for
  callers that never produced one).

These tests pin every cell of the four-headers x cookie-present matrix.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Request

from features.authentication.adapters.inbound.http.auth import _enforce_cookie_origin
from features.authentication.adapters.inbound.http.cookies import REFRESH_COOKIE_NAME

pytestmark = pytest.mark.unit

TRUSTED_ORIGIN = "https://app.example.com"
UNTRUSTED_ORIGIN = "https://evil.example.com"


def _build_request(
    *,
    origin: str | None,
    referer: str | None,
    refresh_cookie: bool,
    cors_origins: list[str] | None = None,
) -> Request:
    """Construct a minimal ASGI ``Request`` carrying the requested headers.

    The wider FastAPI stack is not exercised — ``_enforce_cookie_origin``
    only reads headers, cookies, and the auth container's settings from
    ``request.app.state``.
    """
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin.encode("latin-1")))
    if referer is not None:
        headers.append((b"referer", referer.encode("latin-1")))
    if refresh_cookie:
        headers.append(
            (b"cookie", f"{REFRESH_COOKIE_NAME}=opaque-token-value".encode("latin-1"))
        )

    container = SimpleNamespace(
        settings=SimpleNamespace(cors_origins=cors_origins or [TRUSTED_ORIGIN])
    )
    state = SimpleNamespace(auth_container=container)
    app = SimpleNamespace(state=state)

    scope: dict[str, object] = {
        "type": "http",
        "method": "POST",
        "path": "/auth/refresh",
        "headers": headers,
        "query_string": b"",
        "app": app,
    }
    return Request(scope)


# ── Origin present ───────────────────────────────────────────────────────────


def test_trusted_origin_passes_with_cookie() -> None:
    request = _build_request(origin=TRUSTED_ORIGIN, referer=None, refresh_cookie=True)
    # Pass: function returns None and does not raise.
    _enforce_cookie_origin(request)


def test_trusted_origin_passes_without_cookie() -> None:
    request = _build_request(origin=TRUSTED_ORIGIN, referer=None, refresh_cookie=False)
    # Pass: function returns None and does not raise.
    _enforce_cookie_origin(request)


def test_untrusted_origin_is_rejected_with_cookie() -> None:
    request = _build_request(origin=UNTRUSTED_ORIGIN, referer=None, refresh_cookie=True)
    with pytest.raises(HTTPException) as exc_info:
        _enforce_cookie_origin(request)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Untrusted origin"


def test_untrusted_origin_is_rejected_without_cookie() -> None:
    """Origin check fires regardless of cookie presence.

    The contract is: if an ``Origin`` header is sent at all, it must be
    trusted. Skipping the check when the cookie is absent would let
    untrusted callers learn whether the endpoint exists by observing a
    200/404 vs 403 difference.
    """
    request = _build_request(
        origin=UNTRUSTED_ORIGIN, referer=None, refresh_cookie=False
    )
    with pytest.raises(HTTPException) as exc_info:
        _enforce_cookie_origin(request)
    assert exc_info.value.status_code == 403


# ── Referer present, Origin absent ────────────────────────────────────────────


def test_trusted_referer_passes_with_cookie() -> None:
    request = _build_request(
        origin=None,
        referer=f"{TRUSTED_ORIGIN}/some/path?q=1",
        refresh_cookie=True,
    )
    # Pass: function returns None and does not raise.
    _enforce_cookie_origin(request)


def test_trusted_referer_passes_without_cookie() -> None:
    request = _build_request(
        origin=None,
        referer=f"{TRUSTED_ORIGIN}/some/path",
        refresh_cookie=False,
    )
    # Pass: function returns None and does not raise.
    _enforce_cookie_origin(request)


def test_untrusted_referer_is_rejected_with_cookie() -> None:
    request = _build_request(
        origin=None,
        referer=f"{UNTRUSTED_ORIGIN}/landing",
        refresh_cookie=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        _enforce_cookie_origin(request)
    assert exc_info.value.status_code == 403


def test_malformed_referer_is_rejected_with_cookie() -> None:
    """A ``Referer`` we can't parse must be treated as untrusted."""
    request = _build_request(
        origin=None,
        referer="not-a-url",
        refresh_cookie=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        _enforce_cookie_origin(request)
    assert exc_info.value.status_code == 403


# ── Both headers present ─────────────────────────────────────────────────────


def test_both_present_origin_takes_precedence_when_origin_trusted() -> None:
    """When ``Origin`` is present and trusted, ``Referer`` is not consulted.

    The current implementation short-circuits on a successful ``Origin``
    match. Even an untrusted ``Referer`` doesn't override the decision.
    """
    request = _build_request(
        origin=TRUSTED_ORIGIN,
        referer=f"{UNTRUSTED_ORIGIN}/foo",
        refresh_cookie=True,
    )
    # Pass: function returns None and does not raise.
    _enforce_cookie_origin(request)


def test_both_present_untrusted_origin_is_rejected_even_with_trusted_referer() -> None:
    """An untrusted ``Origin`` is decisive — the ``Referer`` does not rescue it."""
    request = _build_request(
        origin=UNTRUSTED_ORIGIN,
        referer=f"{TRUSTED_ORIGIN}/foo",
        refresh_cookie=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        _enforce_cookie_origin(request)
    assert exc_info.value.status_code == 403


def test_both_present_without_cookie_origin_trusted() -> None:
    request = _build_request(
        origin=TRUSTED_ORIGIN,
        referer=f"{TRUSTED_ORIGIN}/foo",
        refresh_cookie=False,
    )
    # Pass: function returns None and does not raise.
    _enforce_cookie_origin(request)


# ── Neither header present ───────────────────────────────────────────────────


def test_neither_header_with_cookie_is_rejected() -> None:
    """When both ``Origin`` and ``Referer`` are missing AND the refresh
    cookie is on the request, the request is refused with 403.

    This is the CSRF-mitigation core: a cookie-authenticated request
    with no provenance signal cannot be trusted.
    """
    request = _build_request(origin=None, referer=None, refresh_cookie=True)
    with pytest.raises(HTTPException) as exc_info:
        _enforce_cookie_origin(request)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Untrusted origin"


def test_neither_header_without_cookie_is_noop() -> None:
    """No refresh cookie → no CSRF surface → no-op (backwards compat).

    Pathological callers (curl with no headers) that do not authenticate
    via the cookie are not blocked by this check.
    """
    request = _build_request(origin=None, referer=None, refresh_cookie=False)
    # Pass: function returns None and does not raise.
    _enforce_cookie_origin(request)


# ── Wildcard CORS (development convenience) ──────────────────────────────────


def test_wildcard_cors_accepts_any_origin_with_cookie() -> None:
    """``cors_origins=["*"]`` short-circuits the trust check when ``Origin``
    is present. Used in development/test only — production validators
    refuse the wildcard.
    """
    request = _build_request(
        origin=UNTRUSTED_ORIGIN,
        referer=None,
        refresh_cookie=True,
        cors_origins=["*"],
    )
    # Pass: function returns None and does not raise.
    _enforce_cookie_origin(request)


def test_wildcard_cors_does_not_bypass_missing_headers_when_cookie_present() -> None:
    """Wildcard CORS does not waive the "no provenance signal" rejection.

    If both ``Origin`` and ``Referer`` are absent and the refresh cookie
    is present, the request must still be refused regardless of CORS
    configuration — there is nothing to validate against.
    """
    request = _build_request(
        origin=None,
        referer=None,
        refresh_cookie=True,
        cors_origins=["*"],
    )
    with pytest.raises(HTTPException) as exc_info:
        _enforce_cookie_origin(request)
    assert exc_info.value.status_code == 403
