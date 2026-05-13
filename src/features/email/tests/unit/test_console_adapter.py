"""Unit tests for :class:`ConsoleEmailAdapter`."""

from __future__ import annotations

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


def test_logs_rendered_email_at_info(
    registry: EmailTemplateRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="features.email.console")
    adapter = ConsoleEmailAdapter(registry=registry)

    result = adapter.send(
        to="alice@example.com",
        template_name="test/welcome",
        context={"name": "Alice"},
    )

    assert isinstance(result, Ok)
    assert "event=email.console.sent" in caplog.text
    assert "to=alice@example.com" in caplog.text
    assert "Welcome, Alice!" in caplog.text


def test_unknown_template_returns_err(registry: EmailTemplateRegistry) -> None:
    adapter = ConsoleEmailAdapter(registry=registry)
    result = adapter.send(
        to="alice@example.com",
        template_name="missing",
        context={},
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, UnknownTemplateError)
