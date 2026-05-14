"""Per-account lockout fires regardless of IP diversity.

Covers task 5.2 from ``harden-rate-limiting``. The per-account limiter
is AND-composed with the existing per-(ip, email) limiter in the route
handlers so an attacker rotating IPs (each under the per-IP burst
budget) still hits an absolute per-account budget. This test exercises
that contract at the helper boundary
(``_check_per_account_rate_limit``) with a fake auth container.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import fastapi
import pytest

from features.authentication.adapters.inbound.http.auth import (
    _account_key,
    _check_per_account_rate_limit,
)
from features.authentication.application.errors import RateLimitExceededError
from features.authentication.application.rate_limit import FixedWindowRateLimiter

pytestmark = pytest.mark.unit


@dataclass(slots=True)
class _FakeSettings:
    auth_rate_limit_enabled: bool = True


@dataclass(slots=True)
class _FakeContainer:
    """Minimal stand-in for ``AuthContainer`` exposing only the fields
    ``_check_per_account_rate_limit`` reads."""

    settings: _FakeSettings = field(default_factory=_FakeSettings)
    per_account_login_limiter: Any = None
    per_account_reset_limiter: Any = None
    per_account_verify_limiter: Any = None


def _make_request(container: _FakeContainer, client_host: str) -> fastapi.Request:
    """Build a Starlette Request with ``request.app.state.auth_container``
    set to ``container`` and ``request.client.host == client_host``."""
    app = fastapi.FastAPI()
    # Attach the container under the same attribute name the production
    # helper reads via ``get_auth_container``.
    app.state.auth_container = container
    scope: dict[str, Any] = {
        "type": "http",
        "method": "POST",
        "path": "/auth/login",
        "headers": [],
        "query_string": b"",
        "client": (client_host, 12345),
        "app": app,
    }
    return fastapi.Request(scope)


def test_account_key_is_independent_of_path_and_ip() -> None:
    """The per-account key must NOT include the path or IP — the whole
    point of the limiter is to enforce a budget independent of those."""
    key_a = _account_key("login", "victim@example.com")
    key_b = _account_key("login", "victim@example.com")
    assert key_a == key_b
    # Action must be part of the key so login/reset/verify don't share
    # a budget.
    assert _account_key("reset", "victim@example.com") != key_a
    # ``None`` collapses to the documented ``"unknown"`` sentinel.
    assert _account_key("login", None) == "per_account:login:unknown"


def test_per_account_limiter_trips_across_distinct_ips() -> None:
    """N failures against the same email from N distinct IPs still trip.

    The per-account limiter does not consult the request IP, so each
    of the N requests counts against the same budget — at attempt N+1
    the limiter raises ``RateLimitExceededError``, which the handler
    surfaces as HTTP 429.
    """
    max_attempts = 3
    limiter = FixedWindowRateLimiter(
        max_attempts=max_attempts,
        window_seconds=60,
    )
    container = _FakeContainer(per_account_login_limiter=limiter)

    distinct_ips = [
        "10.0.0.1",
        "10.0.0.2",
        "10.0.0.3",  # botnet of three distinct IPs
    ]
    assert len(distinct_ips) == max_attempts

    # All ``max_attempts`` attempts (one per distinct IP) must pass.
    for ip in distinct_ips:
        request = _make_request(container, client_host=ip)
        _check_per_account_rate_limit(request, "login", "victim@example.com")

    # The next attempt — yet another distinct IP — MUST trip the limiter.
    request = _make_request(container, client_host="10.0.0.4")
    with pytest.raises(fastapi.HTTPException) as exc_info:
        _check_per_account_rate_limit(request, "login", "victim@example.com")

    assert exc_info.value.status_code == 429


def test_per_account_limiter_distinct_emails_have_independent_budgets() -> None:
    """Per-account limiter is keyed on identifier — distinct emails do not
    share state. Sanity check so the lockout cannot be used to DoS
    other users.
    """
    limiter = FixedWindowRateLimiter(max_attempts=2, window_seconds=60)
    container = _FakeContainer(per_account_login_limiter=limiter)

    # Burn the budget for victim@example.com from a single IP.
    request = _make_request(container, client_host="10.0.0.1")
    _check_per_account_rate_limit(request, "login", "victim@example.com")
    _check_per_account_rate_limit(request, "login", "victim@example.com")

    # Another email's budget is untouched.
    _check_per_account_rate_limit(request, "login", "other@example.com")


def test_per_account_limiter_distinct_actions_have_independent_budgets() -> None:
    """``login``, ``reset``, and ``verify`` budgets are independent.

    A burned login budget must not block password-reset requests for
    the same email — the budgets are tuned independently (login is
    bursty; reset is rarely intentional).
    """
    login_limiter = FixedWindowRateLimiter(max_attempts=1, window_seconds=60)
    reset_limiter = FixedWindowRateLimiter(max_attempts=1, window_seconds=60)
    container = _FakeContainer(
        per_account_login_limiter=login_limiter,
        per_account_reset_limiter=reset_limiter,
    )

    request = _make_request(container, client_host="10.0.0.1")
    _check_per_account_rate_limit(request, "login", "victim@example.com")

    # Login budget is now spent for this email…
    with pytest.raises(fastapi.HTTPException):
        _check_per_account_rate_limit(request, "login", "victim@example.com")

    # …but reset still has a full budget — they are separate limiters.
    _check_per_account_rate_limit(request, "reset", "victim@example.com")


def test_per_account_limiter_skipped_when_rate_limit_disabled() -> None:
    """``auth_rate_limit_enabled=False`` must short-circuit the check.

    The test settings fixture sets this to ``False`` so e2e tests
    are not constrained by the limiter; this assertion guards against
    a regression that would silently enable the check.
    """
    # A limiter with ``max_attempts=0`` raises on every call — so if
    # the helper is honouring the kill switch, this call must NOT raise.
    poisoned = FixedWindowRateLimiter(max_attempts=0, window_seconds=60)
    container = _FakeContainer(
        settings=_FakeSettings(auth_rate_limit_enabled=False),
        per_account_login_limiter=poisoned,
    )
    request = _make_request(container, client_host="10.0.0.1")
    # No raise.
    _check_per_account_rate_limit(request, "login", "victim@example.com")


def test_per_account_limiter_rejects_unknown_action() -> None:
    """An action the wiring does not recognise is a programmer error.

    The helper raises ``ValueError`` so the bug surfaces immediately
    rather than silently selecting the wrong limiter.
    """
    container = _FakeContainer(
        per_account_login_limiter=FixedWindowRateLimiter(),
    )
    request = _make_request(container, client_host="10.0.0.1")
    with pytest.raises(ValueError, match="unknown per-account rate-limit action"):
        _check_per_account_rate_limit(request, "delete", "victim@example.com")


def test_per_account_limiter_uses_action_specific_limiter() -> None:
    """``action="verify"`` MUST hit the verify limiter, not login.

    Sanity check that the switch in the helper picks the right
    limiter — a swap would silently mix budgets across actions.
    """
    login_limiter = FixedWindowRateLimiter(max_attempts=100, window_seconds=60)
    verify_limiter = FixedWindowRateLimiter(max_attempts=1, window_seconds=60)
    container = _FakeContainer(
        per_account_login_limiter=login_limiter,
        per_account_verify_limiter=verify_limiter,
    )
    request = _make_request(container, client_host="10.0.0.1")

    _check_per_account_rate_limit(request, "verify", "victim@example.com")
    with pytest.raises(fastapi.HTTPException):
        _check_per_account_rate_limit(request, "verify", "victim@example.com")

    # The login limiter MUST still be untouched.
    try:
        login_limiter.check("per_account:login:victim@example.com")
    except RateLimitExceededError as exc:  # pragma: no cover - sanity
        pytest.fail(f"login limiter was modified by verify call: {exc}")
