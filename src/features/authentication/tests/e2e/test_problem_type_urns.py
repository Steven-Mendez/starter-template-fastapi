"""Per-error-class assertions that responses carry the right Problem Type URN.

Covers task list 4.1.a-4.1.i in
``openspec/changes/add-stable-problem-types``: each public error path
must emit a stable ``type`` URN so SDKs branch on it rather than
parsing ``detail``.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlmodel import Session

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.dependencies.container import set_app_container
from app_platform.api.problem_types import ProblemType
from app_platform.config.settings import AppSettings
from features.authentication.tests.e2e.conftest import AuthTestContext
from features.users.adapters.outbound.persistence.sqlmodel.models import UserTable

pytestmark = pytest.mark.e2e

_RATE_LIMIT_ATTEMPTS_BEFORE_429 = 5


def _register(client: TestClient, email: str = "user@example.com") -> dict[str, Any]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "UserPassword123!"},
    )
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


def _login(
    client: TestClient,
    email: str = "user@example.com",
    password: str = "UserPassword123!",
) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return str(response.json()["access_token"])


# 4.1.a — invalid credentials
def test_invalid_credentials_returns_auth_invalid_credentials_urn(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    _register(client)
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert (
        response.json()["type"]
        == ProblemType.AUTH_INVALID_CREDENTIALS.value
        == "urn:problem:auth:invalid-credentials"
    )


# 4.1.b — rate limited
def test_rate_limited_login_returns_auth_rate_limited_urn(
    auth_context_rate_limited: AuthTestContext,
) -> None:
    client = auth_context_rate_limited.client
    body = {"email": "user@example.com", "password": "wrong-password"}
    for _ in range(_RATE_LIMIT_ATTEMPTS_BEFORE_429):
        client.post("/auth/login", json=body)
    blocked = client.post("/auth/login", json=body)
    assert blocked.status_code == 429
    assert (
        blocked.json()["type"]
        == ProblemType.AUTH_RATE_LIMITED.value
        == "urn:problem:auth:rate-limited"
    )


# 4.1.c — stale token
def test_stale_token_returns_auth_token_stale_urn(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    user = _register(client)
    token = _login(client)
    user_id = UUID(user["id"])
    # Bumping the authz_version stales the issued token.
    auth_context.user_repository.set_active(user_id, is_active=True)

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert (
        response.json()["type"]
        == ProblemType.AUTH_TOKEN_STALE.value
        == "urn:problem:auth:token-stale"
    )


# 4.1.d — invalid token (malformed Bearer)
def test_malformed_bearer_returns_auth_token_invalid_urn(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    response = client.get(
        "/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )
    assert response.status_code == 401
    assert (
        response.json()["type"]
        == ProblemType.AUTH_TOKEN_INVALID.value
        == "urn:problem:auth:token-invalid"
    )


# 4.1.e — email not verified
def test_login_with_unverified_email_returns_email_not_verified_urn(
    auth_context_email_verification_required: AuthTestContext,
) -> None:
    client = auth_context_email_verification_required.client
    _register(client, "verify-required@example.com")

    response = client.post(
        "/auth/login",
        json={"email": "verify-required@example.com", "password": "UserPassword123!"},
    )
    assert response.status_code == 403
    assert (
        response.json()["type"]
        == ProblemType.AUTH_EMAIL_NOT_VERIFIED.value
        == "urn:problem:auth:email-not-verified"
    )


# 4.1.f — permission denied (non-admin on /admin/users)
def test_non_admin_on_admin_users_returns_authz_permission_denied_urn(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    _register(client, "regular@example.com")
    token = _login(client, email="regular@example.com")
    response = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert (
        response.json()["type"]
        == ProblemType.AUTHZ_PERMISSION_DENIED.value
        == "urn:problem:authz:permission-denied"
    )


# 4.1.g — validation failed (malformed PATCH /me body)
def test_malformed_patch_me_body_returns_validation_failed_urn(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    _register(client)
    token = _login(client)
    # ``email`` is typed ``str | None`` on :class:`UpdateProfileRequest`;
    # an integer payload fails Pydantic validation before the use case
    # is invoked.
    response = client.patch(
        "/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": 12345},
    )
    assert response.status_code == 422
    assert (
        response.json()["type"]
        == ProblemType.VALIDATION_FAILED.value
        == "urn:problem:validation:failed"
    )


# 4.1.h — generic not-found (UserNotFoundError on GET /me after self-delete)
def test_user_not_found_returns_generic_not_found_urn(
    auth_context: AuthTestContext,
) -> None:
    # Easiest reproducible path: register, log in, hard-delete the user
    # row via the test repository, then call GET /me with the still-valid
    # token. The use case returns ``Err(UserNotFoundError)`` and the
    # users-feature error mapper sets the URN.
    client = auth_context.client
    user = _register(client, "doomed@example.com")
    token = _login(client, email="doomed@example.com")
    user_id = UUID(user["id"])
    # Warm the principal cache so resolve_principal short-circuits past
    # the user lookup on the second request.
    warmup = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert warmup.status_code == 200
    # Now mark the user erased. ``GetUserById`` (called by the route
    # handler) returns ``UserNotFoundError`` because ``get_by_id`` filters
    # erased rows out, but resolve_principal is bypassed thanks to the
    # principal cache hit above.
    with Session(auth_context.user_repository.engine) as session:
        row = session.get(UserTable, user_id)
        assert row is not None
        row.is_erased = True
        session.add(row)
        session.commit()

    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert (
        response.json()["type"]
        == ProblemType.GENERIC_NOT_FOUND.value
        == "urn:problem:generic:not-found"
    )


# 4.1.i — generic conflict (duplicate registration)
def test_duplicate_registration_returns_generic_conflict_urn(
    auth_context: AuthTestContext,
) -> None:
    client = auth_context.client
    _register(client)
    duplicate = client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "UserPassword123!"},
    )
    assert duplicate.status_code == 409
    assert (
        duplicate.json()["type"]
        == ProblemType.GENERIC_CONFLICT.value
        == "urn:problem:generic:conflict"
    )


# 4.2 — about:blank fallback
@dataclass(frozen=True, slots=True)
class _PlatformContainer:
    settings: AppSettings


def _build_uncategorized_app(settings: AppSettings) -> FastAPI:
    """Build a minimal app exposing an endpoint that raises a non-domain exception.

    Used to verify that genuinely uncategorized failures still produce
    ``type: "about:blank"`` (the spec-compliant fallback) and that
    ``ProblemType.ABOUT_BLANK`` is exactly that string.
    """
    app = build_fastapi_app(settings)

    class _Body(BaseModel):
        value: int

    @app.get("/__uncategorized")
    def _boom() -> dict[str, str]:
        raise RuntimeError("uncategorized")

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(lifespan_app, _PlatformContainer(settings=settings))
        yield
        lifespan_app.state.container = None

    app.router.lifespan_context = lifespan
    return app


@pytest.fixture
def uncategorized_client(test_settings: AppSettings) -> Iterator[TestClient]:
    with TestClient(
        _build_uncategorized_app(test_settings),
        raise_server_exceptions=False,
    ) as c:
        yield c


def test_about_blank_value_and_fallback(uncategorized_client: TestClient) -> None:
    # ProblemType.ABOUT_BLANK is the literal RFC 9457 sentinel string.
    assert ProblemType.ABOUT_BLANK.value == "about:blank"
    assert str(ProblemType.ABOUT_BLANK) == "about:blank"
    # And the platform unhandled-exception handler emits it verbatim.
    response = uncategorized_client.get("/__uncategorized")
    assert response.status_code == 500
    assert response.json()["type"] == "about:blank"
