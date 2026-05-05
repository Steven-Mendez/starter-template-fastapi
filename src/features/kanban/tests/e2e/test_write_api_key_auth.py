from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.e2e


def test_post_without_key_is_401(secured_client: TestClient) -> None:
    resp = secured_client.post("/api/boards", json={"title": "x"})
    assert resp.status_code == 401


def test_post_with_wrong_key_is_401(secured_client: TestClient) -> None:
    resp = secured_client.post(
        "/api/boards", json={"title": "x"}, headers={"X-API-Key": "nope"}
    )
    assert resp.status_code == 401


def test_post_with_correct_key_succeeds(secured_client: TestClient) -> None:
    resp = secured_client.post(
        "/api/boards",
        json={"title": "ok"},
        headers={"X-API-Key": "secret"},
    )
    assert resp.status_code == 201


def test_get_does_not_require_key(secured_client: TestClient) -> None:
    resp = secured_client.get("/api/boards")
    assert resp.status_code == 200


def test_no_write_key_means_no_auth(client: TestClient) -> None:
    resp = client.post("/api/boards", json={"title": "ok"})
    assert resp.status_code == 201
