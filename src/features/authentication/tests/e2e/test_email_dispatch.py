"""End-to-end coverage for the email feature wired into the auth flows."""

from __future__ import annotations

import pytest

from src.features.authentication.email_templates import (
    PASSWORD_RESET_TEMPLATE,
    VERIFY_EMAIL_TEMPLATE,
)
from src.features.authentication.tests.e2e.conftest import AuthTestContext

pytestmark = pytest.mark.e2e


def _register(context: AuthTestContext, email: str = "user@example.com") -> None:
    response = context.client.post(
        "/auth/register",
        json={"email": email, "password": "UserPassword123!"},
    )
    assert response.status_code == 201


def test_password_reset_returns_202_with_no_token_when_hidden(
    auth_context_internal_tokens_hidden: AuthTestContext,
) -> None:
    """Per the email spec: status 202 and no token in the body."""
    context = auth_context_internal_tokens_hidden
    _register(context)
    context.email.reset()

    response = context.client.post(
        "/auth/password/forgot", json={"email": "user@example.com"}
    )

    assert response.status_code == 202
    body = response.json()
    assert body["dev_token"] is None

    # The use case rendered and dispatched the password-reset email via
    # the wired EmailPort — the fake recorded it.
    assert len(context.email.sent) == 1
    sent = context.email.sent[0]
    assert sent.template_name == PASSWORD_RESET_TEMPLATE
    assert sent.to == "user@example.com"
    assert "reset_url" in sent.context


def test_email_verify_request_dispatches_email(
    auth_context: AuthTestContext,
) -> None:
    """Authenticated verification request enqueues the verify-email template."""
    client = auth_context.client
    _register(auth_context)
    auth_context.email.reset()

    login = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "UserPassword123!"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.post(
        "/auth/email/verify/request",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 202
    assert len(auth_context.email.sent) == 1
    sent = auth_context.email.sent[0]
    assert sent.template_name == VERIFY_EMAIL_TEMPLATE
    assert sent.to == "user@example.com"
    assert "verify_url" in sent.context


def test_password_reset_for_unknown_email_does_not_send(
    auth_context: AuthTestContext,
) -> None:
    """Unknown email returns 202 (anti-enumeration) but does NOT send mail."""
    auth_context.email.reset()

    response = auth_context.client.post(
        "/auth/password/forgot", json={"email": "missing@example.com"}
    )

    assert response.status_code == 202
    assert auth_context.email.sent == []
