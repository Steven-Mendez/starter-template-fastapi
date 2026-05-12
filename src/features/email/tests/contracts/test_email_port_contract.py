"""Behavioural contract shared by every :class:`EmailPort` implementation.

Each adapter under test is exercised against the same scenarios so a
new adapter (Mailgun, SES, etc.) can be plugged in by extending the
parametrisation.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Callable

import httpx
import pytest
import respx

from src.features.email.adapters.outbound.console import ConsoleEmailAdapter
from src.features.email.adapters.outbound.resend import ResendEmailAdapter
from src.features.email.application.errors import UnknownTemplateError
from src.features.email.application.ports.email_port import EmailPort
from src.features.email.application.registry import EmailTemplateRegistry
from src.features.email.tests.fakes.fake_email_port import FakeEmailPort
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


AdapterFactory = Callable[[EmailTemplateRegistry], EmailPort]

_RESEND_BASE_URL = "https://api.resend.com"


def _console_factory(registry: EmailTemplateRegistry) -> EmailPort:
    return ConsoleEmailAdapter(registry=registry)


def _fake_factory(_: EmailTemplateRegistry) -> EmailPort:
    # The fake doesn't consult the registry, but the contract still asks
    # what happens with valid input — for the fake, "valid" is anything.
    return FakeEmailPort()


def _resend_factory(registry: EmailTemplateRegistry) -> EmailPort:
    return ResendEmailAdapter(
        registry=registry,
        api_key="test-key",
        from_address="no-reply@example.com",
        base_url=_RESEND_BASE_URL,
    )


@pytest.fixture
def registry(tmp_path: Path) -> EmailTemplateRegistry:
    body = tmp_path / "msg.txt"
    body.write_text("Hi {{ name }}\n")
    registry = EmailTemplateRegistry()
    registry.register_template("contract/msg", subject="hi", body_path=body)
    return registry


@pytest.fixture
def resend_mock() -> Iterator[respx.MockRouter]:
    """Respx-mocked Resend endpoint that returns 200 for the happy path."""
    with respx.mock(base_url=_RESEND_BASE_URL, assert_all_called=False) as mock:
        mock.post("/emails").mock(return_value=httpx.Response(200, json={"id": "ok"}))
        yield mock


@pytest.mark.parametrize(
    "factory",
    [_console_factory, _fake_factory, _resend_factory],
    ids=["console", "fake", "resend"],
)
def test_valid_send_returns_ok(
    factory: AdapterFactory,
    registry: EmailTemplateRegistry,
    resend_mock: respx.MockRouter,
) -> None:
    port = factory(registry)
    result = port.send(
        to="a@example.com",
        template_name="contract/msg",
        context={"name": "A"},
    )
    assert isinstance(result, Ok)


def test_console_send_with_unknown_template_returns_err(
    registry: EmailTemplateRegistry,
) -> None:
    """The fake skips registry lookup; the console adapter enforces it."""
    port = _console_factory(registry)
    result = port.send(
        to="a@example.com",
        template_name="never-registered",
        context={},
    )
    assert isinstance(result, Err)
    assert isinstance(result.error, UnknownTemplateError)
