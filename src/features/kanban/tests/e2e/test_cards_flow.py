"""End-to-end tests for cards flow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def _seed_column(client: TestClient) -> tuple[str, str]:
    board = client.post("/api/boards", json={"title": "B"}).json()
    column = client.post(
        f"/api/boards/{board['id']}/columns", json={"title": "todo"}
    ).json()
    return board["id"], column["id"]


def test_create_card(client: TestClient) -> None:
    _, column_id = _seed_column(client)
    resp = client.post(
        f"/api/columns/{column_id}/cards",
        json={"title": "task", "priority": "high"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "task"
    assert body["priority"] == "high"


def test_get_card(client: TestClient) -> None:
    _, column_id = _seed_column(client)
    created = client.post(f"/api/columns/{column_id}/cards", json={"title": "t"}).json()
    resp = client.get(f"/api/cards/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "t"


def test_get_unknown_card_returns_403_not_404(client: TestClient) -> None:
    """Under ReBAC, unauthorized access returns 403 even for non-existent ids."""
    resp = client.get("/api/cards/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 403


def test_patch_card_clear_due_at(client: TestClient) -> None:
    _, column_id = _seed_column(client)
    created = client.post(
        f"/api/columns/{column_id}/cards",
        json={"title": "t", "due_at": "2026-12-01T00:00:00Z"},
    ).json()
    resp = client.patch(f"/api/cards/{created['id']}", json={"due_at": None})
    assert resp.status_code == 200
    assert resp.json()["due_at"] is None


def test_create_card_under_unknown_column_is_403(client: TestClient) -> None:
    """Authorization runs before the use case, so an unknown column returns 403."""
    resp = client.post(
        "/api/columns/00000000-0000-0000-0000-000000000000/cards",
        json={"title": "t"},
    )
    assert resp.status_code == 403
