"""End-to-end tests for boards flow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def test_create_board_returns_201_and_payload(client: TestClient) -> None:
    resp = client.post("/api/boards", json={"title": "Roadmap"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Roadmap"
    assert isinstance(body["id"], str)


def test_get_unknown_board_returns_problem_404(client: TestClient) -> None:
    resp = client.get("/api/boards/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["code"] == "board_not_found"
    assert body["instance"].endswith("/api/boards/00000000-0000-0000-0000-000000000000")
    assert "request_id" in body


def test_list_boards_returns_array(client: TestClient) -> None:
    client.post("/api/boards", json={"title": "A"})
    client.post("/api/boards", json={"title": "B"})
    resp = client.get("/api/boards")
    assert resp.status_code == 200
    titles = sorted(b["title"] for b in resp.json())
    assert titles == ["A", "B"]


def test_patch_board_renames(client: TestClient) -> None:
    created = client.post("/api/boards", json={"title": "orig"}).json()
    resp = client.patch(f"/api/boards/{created['id']}", json={"title": "renamed"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "renamed"


def test_patch_board_no_changes_returns_422(client: TestClient) -> None:
    created = client.post("/api/boards", json={"title": "x"}).json()
    resp = client.patch(f"/api/boards/{created['id']}", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "patch_no_changes"


def test_delete_board(client: TestClient) -> None:
    created = client.post("/api/boards", json={"title": "x"}).json()
    resp = client.delete(f"/api/boards/{created['id']}")
    assert resp.status_code == 204
    follow_up = client.get(f"/api/boards/{created['id']}")
    assert follow_up.status_code == 404


def test_validation_error_is_problem_422(client: TestClient) -> None:
    resp = client.post("/api/boards", json={"title": ""})
    assert resp.status_code == 422
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["status"] == 422
    assert "errors" in body


def test_request_id_propagated(client: TestClient) -> None:
    resp = client.get("/api/boards", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Request-ID"] == "abc-123"


def test_request_id_generated_when_missing(client: TestClient) -> None:
    resp = client.get("/api/boards")
    assert resp.headers["X-Request-ID"]
