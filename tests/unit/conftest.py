"""Unit-only fixtures for Kanban command/query setup and test builders."""

from __future__ import annotations

import pytest

from tests.support.kanban_builders import HandlerHarness


@pytest.fixture
def handler_harness() -> HandlerHarness:
    return HandlerHarness.build_default()
