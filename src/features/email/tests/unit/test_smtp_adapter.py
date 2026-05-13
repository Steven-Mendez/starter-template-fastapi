"""Unit tests for :class:`SmtpEmailAdapter` using an in-process aiosmtpd server."""

from __future__ import annotations

import asyncio
import socket
import threading
from pathlib import Path
from typing import Any

import pytest
from aiosmtpd.controller import Controller

from app_platform.shared.result import Err, Ok
from features.email.adapters.outbound.smtp import SmtpEmailAdapter
from features.email.application.errors import DeliveryError
from features.email.application.registry import EmailTemplateRegistry

pytestmark = pytest.mark.unit


class _RecordingHandler:
    """aiosmtpd handler that captures every received envelope."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:  # noqa: N802
        self.messages.append(
            {
                "from": envelope.mail_from,
                "to": list(envelope.rcpt_tos),
                "body": envelope.content.decode("utf-8", errors="replace"),
            }
        )
        return "250 OK"


def _free_port() -> int:
    """Allocate a free TCP port on localhost.

    aiosmtpd's Controller pre-binds to verify reachability and does not
    re-read the assigned port from a ``port=0`` socket on macOS, so we
    pick a port up front instead.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()


@pytest.fixture
def smtp_server() -> Any:
    """Start an aiosmtpd server bound to a random port; tear down after test."""
    handler = _RecordingHandler()
    controller = Controller(handler, hostname="127.0.0.1", port=_free_port())
    controller.start()
    try:
        yield handler, controller
    finally:
        controller.stop()


@pytest.fixture
def registry(tmp_path: Path) -> EmailTemplateRegistry:
    body = tmp_path / "welcome.txt"
    body.write_text("Welcome, {{ name }}!\n")
    registry = EmailTemplateRegistry()
    registry.register_template(
        "test/welcome", subject="Hello {{ name }}", body_path=body
    )
    return registry


def test_sends_via_smtp_server(
    smtp_server: tuple[_RecordingHandler, Controller],
    registry: EmailTemplateRegistry,
) -> None:
    handler, controller = smtp_server
    adapter = SmtpEmailAdapter(
        registry=registry,
        host=controller.hostname,
        port=controller.port,
        from_address="no-reply@example.com",
        use_starttls=False,
        use_ssl=False,
    )

    # The adapter performs blocking SMTP I/O; run on a worker so the
    # asyncio loop driving aiosmtpd stays free.
    sent: list[Any] = []

    def _send() -> None:
        sent.append(
            adapter.send(
                to="alice@example.com",
                template_name="test/welcome",
                context={"name": "Alice"},
            )
        )

    t = threading.Thread(target=_send)
    t.start()
    t.join(timeout=5.0)

    assert isinstance(sent[0], Ok)
    assert len(handler.messages) == 1
    assert handler.messages[0]["to"] == ["alice@example.com"]
    assert "Welcome, Alice!" in handler.messages[0]["body"]


def test_returns_err_on_unreachable_server(
    registry: EmailTemplateRegistry,
) -> None:
    adapter = SmtpEmailAdapter(
        registry=registry,
        host="127.0.0.1",
        port=1,  # No process listens here.
        from_address="no-reply@example.com",
        use_starttls=False,
        use_ssl=False,
        timeout=0.5,
    )

    result = adapter.send(
        to="alice@example.com",
        template_name="test/welcome",
        context={"name": "Alice"},
    )

    assert isinstance(result, Err)
    assert isinstance(result.error, DeliveryError)


def _silence_unused_asyncio_warning() -> None:  # pragma: no cover
    # aiosmtpd may schedule pending tasks on the running event loop; drain
    # them defensively to keep pytest-asyncio output clean.
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    pending = asyncio.all_tasks(loop) if not loop.is_closed() else set()
    for task in pending:
        task.cancel()
