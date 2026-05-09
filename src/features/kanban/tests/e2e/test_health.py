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
    assert body["auth"]["jwt_secret_configured"] is True
    assert body["auth"]["principal_cache_ready"] is True
    assert body["auth"]["rate_limiter_ready"] is True


def test_health_degraded(client: TestClient, wiring: FakeKanbanWiring) -> None:
    wiring.repository.set_ready(False)
    resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["persistence"]["ready"] is False


def test_health_degraded_without_jwt_secret(
    client_without_jwt_secret: TestClient,
) -> None:
    resp = client_without_jwt_secret.get("/health")
    assert resp.status_code == 503
    assert resp.json()["auth"]["jwt_secret_configured"] is False


def test_health_degraded_when_configured_redis_is_unreachable(
    client_with_unreachable_redis: TestClient,
) -> None:
    resp = client_with_unreachable_redis.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["redis"] == {"configured": True, "ready": False}
    assert body["auth"]["rate_limiter_backend"] == "redis"
    assert body["auth"]["rate_limiter_ready"] is False


def test_liveness_always_returns_200(client: TestClient) -> None:
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_liveness_returns_200_even_when_db_is_down(
    client: TestClient, wiring: FakeKanbanWiring
) -> None:
    wiring.repository.set_ready(False)
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_readiness_ready_route_matches_health_alias(client: TestClient) -> None:
    ready_resp = client.get("/health/ready")
    alias_resp = client.get("/health")
    assert ready_resp.status_code == alias_resp.status_code
    assert ready_resp.json() == alias_resp.json()


def test_readiness_returns_503_when_degraded(
    client: TestClient, wiring: FakeKanbanWiring
) -> None:
    wiring.repository.set_ready(False)
    assert client.get("/health/ready").status_code == 503
