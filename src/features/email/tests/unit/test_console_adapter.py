"""Unit tests for :class:`ConsoleEmailAdapter`.

Tasks 6.1 and the implementer-flagged rewrite of
``test_logs_rendered_email_at_info`` live here. The default-off log
posture is the contract that prevents reset/verify tokens from
appearing in INFO lines: the adapter MUST emit ``body_sha256=`` (so
operators can correlate), MUST redact ``to`` through
:func:`redact_email`, and MUST NOT emit the raw body unless the
caller explicitly opts in (``log_bodies=True``) AND the environment
is ``"development"``.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import pytest

from app_platform.shared.result import Err, Ok
from features.email.adapters.outbound.console import ConsoleEmailAdapter
from features.email.application.errors import UnknownTemplateError
from features.email.application.registry import EmailTemplateRegistry

pytestmark = pytest.mark.unit


@pytest.fixture
def registry(tmp_path: Path) -> EmailTemplateRegistry:
    body = tmp_path / "welcome.txt"
    body.write_text("Welcome, {{ name }}!\n")
    registry = EmailTemplateRegistry()
    registry.register_template(
        "test/welcome", subject="Hello {{ name }}", body_path=body
    )
    return registry


@pytest.fixture
def reset_registry(tmp_path: Path) -> EmailTemplateRegistry:
    """Registry with a reset-style template whose body contains a token URL.

    The body shape mirrors ``authentication/password_reset``: a literal
    ``reset_url`` rendered into the body. Asserting that the URL never
    appears in the captured log line is the actual contract the
    redaction change exists to enforce.
    """
    body = tmp_path / "password_reset.txt"
    body.write_text("Click {{ reset_url }} to reset.\n")
    registry = EmailTemplateRegistry()
    registry.register_template(
        "authentication/password_reset",
        subject="Reset your password",
        body_path=body,
    )
    return registry


def test_logs_rendered_email_at_info(
    registry: EmailTemplateRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    """Default-off body logging: sha present, ``to`` redacted, body absent.

    Implementer-flagged rewrite of the prior assertion (the old test
    asserted on ``to=alice@example.com`` and the raw body, both of
    which are now forbidden by the redaction contract).
    """
    caplog.set_level(logging.INFO, logger="features.email.console")
    adapter = ConsoleEmailAdapter(registry=registry)

    result = adapter.send(
        to="alice@example.com",
        template_name="test/welcome",
        context={"name": "Alice"},
    )

    assert isinstance(result, Ok)
    assert "event=email.console.sent" in caplog.text
    # body_sha256 must be present so operators can correlate.
    assert "body_sha256=" in caplog.text
    expected_sha = hashlib.sha256(b"Welcome, Alice!\n").hexdigest()
    assert expected_sha in caplog.text
    # ``to`` is redacted (local-part masked, domain preserved).
    assert "to=a***@example.com" in caplog.text
    # The raw email MUST NOT appear.
    assert "alice@example.com" not in caplog.text
    # The raw body MUST NOT appear when ``log_bodies`` is False.
    assert "Welcome, Alice!" not in caplog.text


def test_body_logged_only_when_opt_in_and_development(
    registry: EmailTemplateRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    """Full-body line requires both ``log_bodies=True`` and dev env."""
    caplog.set_level(logging.INFO, logger="features.email.console")
    adapter = ConsoleEmailAdapter(
        registry=registry, log_bodies=True, environment="development"
    )

    result = adapter.send(
        to="alice@example.com",
        template_name="test/welcome",
        context={"name": "Alice"},
    )

    assert isinstance(result, Ok)
    # The full body now appears in the dev-only body line.
    assert "Welcome, Alice!" in caplog.text
    # ``to`` is still redacted on both lines.
    assert "alice@example.com" not in caplog.text


def test_body_not_logged_when_opt_in_outside_development(
    registry: EmailTemplateRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    """``log_bodies=True`` alone is not enough — the env guard must also hold."""
    caplog.set_level(logging.INFO, logger="features.email.console")
    adapter = ConsoleEmailAdapter(
        registry=registry, log_bodies=True, environment="production"
    )

    result = adapter.send(
        to="alice@example.com",
        template_name="test/welcome",
        context={"name": "Alice"},
    )

    assert isinstance(result, Ok)
    # The raw body MUST NOT appear outside development even with the flag on.
    assert "Welcome, Alice!" not in caplog.text


def test_password_reset_log_omits_token_url(
    reset_registry: EmailTemplateRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    """Task 6.1: a reset-template send leaves no raw URL / token in the log.

    Drives the actual leak scenario the change is closing: anyone with
    log read access could complete a reset they did not request if the
    body landed in INFO. With the default-off posture we should see
    ``body_sha256=`` instead.
    """
    caplog.set_level(logging.INFO, logger="features.email.console")
    adapter = ConsoleEmailAdapter(registry=reset_registry)
    reset_url = "https://app.example.com/reset?token=secret-single-use-token-123abc"

    result = adapter.send(
        to="alice@example.com",
        template_name="authentication/password_reset",
        context={"reset_url": reset_url},
    )

    assert isinstance(result, Ok)
    assert "body_sha256=" in caplog.text
    assert reset_url not in caplog.text
    assert "secret-single-use-token-123abc" not in caplog.text


def test_unknown_template_returns_err(registry: EmailTemplateRegistry) -> None:
    adapter = ConsoleEmailAdapter(registry=registry)
    result = adapter.send(
        to="alice@example.com",
        template_name="missing",
        context={},
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, UnknownTemplateError)
