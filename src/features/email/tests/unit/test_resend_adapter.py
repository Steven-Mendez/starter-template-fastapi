"""Targeted unit tests for :class:`ResendEmailAdapter`.

Covers the HTTP-status mapping (4xx, 5xx, transport errors), the
short-circuit on unknown templates, and the custom ``base_url`` knob.
The shared contract suite handles the happy path.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx

from src.features.email.adapters.outbound.resend import ResendEmailAdapter
from src.features.email.application.errors import (
    DeliveryError,
    UnknownTemplateError,
)
from src.features.email.application.registry import EmailTemplateRegistry
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


_BASE_URL = "https://api.resend.com"
_EU_BASE_URL = "https://api.eu.resend.com"


@pytest.fixture
def registry(tmp_path: Path) -> EmailTemplateRegistry:
    body = tmp_path / "msg.txt"
    body.write_text("Hi {{ name }}\n")
    registry = EmailTemplateRegistry()
    registry.register_template("contract/msg", subject="hi", body_path=body)
    return registry


@pytest.fixture
def adapter(registry: EmailTemplateRegistry) -> ResendEmailAdapter:
    return ResendEmailAdapter(
        registry=registry,
        api_key="test-key",
        from_address="no-reply@example.com",
        base_url=_BASE_URL,
    )


@pytest.fixture
def mocked() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=_BASE_URL, assert_all_called=False) as mock:
        yield mock


def test_4xx_returns_delivery_error_with_status_and_message(
    adapter: ResendEmailAdapter, mocked: respx.MockRouter
) -> None:
    mocked.post("/emails").mock(
        return_value=httpx.Response(422, json={"message": "invalid recipient"})
    )

    result = adapter.send(
        to="a@example.com", template_name="contract/msg", context={"name": "A"}
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, DeliveryError)
    assert "422" in result.error.reason
    assert "invalid recipient" in result.error.reason


def test_5xx_returns_delivery_error_without_retry(
    adapter: ResendEmailAdapter, mocked: respx.MockRouter
) -> None:
    route = mocked.post("/emails").mock(return_value=httpx.Response(503))

    result = adapter.send(
        to="a@example.com", template_name="contract/msg", context={"name": "A"}
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, DeliveryError)
    assert "503" in result.error.reason
    assert route.call_count == 1, "adapter must not retry 5xx responses"


def test_transport_error_returns_delivery_error(
    adapter: ResendEmailAdapter, mocked: respx.MockRouter
) -> None:
    mocked.post("/emails").mock(side_effect=httpx.ConnectError("boom"))

    result = adapter.send(
        to="a@example.com", template_name="contract/msg", context={"name": "A"}
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, DeliveryError)
    assert "boom" in result.error.reason


def test_unknown_template_short_circuits_without_http(
    adapter: ResendEmailAdapter, mocked: respx.MockRouter
) -> None:
    route = mocked.post("/emails")

    result = adapter.send(
        to="a@example.com", template_name="never-registered", context={}
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, UnknownTemplateError)
    assert route.call_count == 0, "no HTTP call should happen for unknown templates"


def test_request_payload_carries_required_resend_fields(
    adapter: ResendEmailAdapter, mocked: respx.MockRouter
) -> None:
    route = mocked.post("/emails").mock(
        return_value=httpx.Response(200, json={"id": "abc"})
    )

    result = adapter.send(
        to="a@example.com",
        template_name="contract/msg",
        context={"name": "A"},
    )

    assert isinstance(result, Ok)
    assert route.call_count == 1
    payload = json.loads(route.calls.last.request.content)
    assert payload == {
        "from": "no-reply@example.com",
        "to": ["a@example.com"],
        "subject": "hi",
        "text": "Hi A\n",
    }
    auth = route.calls.last.request.headers.get("Authorization")
    assert auth == "Bearer test-key"


def test_custom_base_url_is_used(registry: EmailTemplateRegistry) -> None:
    adapter = ResendEmailAdapter(
        registry=registry,
        api_key="test-key",
        from_address="no-reply@example.com",
        base_url=_EU_BASE_URL,
    )
    with respx.mock(base_url=_EU_BASE_URL, assert_all_called=False) as mock:
        route = mock.post("/emails").mock(
            return_value=httpx.Response(200, json={"id": "abc"})
        )

        result = adapter.send(
            to="a@example.com",
            template_name="contract/msg",
            context={"name": "A"},
        )

    assert isinstance(result, Ok)
    assert route.call_count == 1
    assert str(route.calls.last.request.url) == f"{_EU_BASE_URL}/emails"
