"""End-to-end tests for health."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.features.kanban.tests.fakes import FakeKanbanWiring

pytestmark = pytest.mark.e2e


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["persistence"]["ready"] is True
    assert body["persistence"]["backend"] == "postgresql"


def test_health_degraded(client: TestClient, wiring: FakeKanbanWiring) -> None:
    wiring.repository.set_ready(False)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["persistence"]["ready"] is False
