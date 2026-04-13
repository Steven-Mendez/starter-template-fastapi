"""RFC 9457 Problem Details (application/problem+json) for API errors."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

_UNKNOWN_BOARD_ID = "00000000-0000-4000-8000-000000000001"


def _assert_problem_json(response) -> dict:
    ctype = response.headers.get("content-type", "")
    assert ctype.startswith("application/problem+json"), ctype
    body = response.json()
    assert "type" in body
    assert "title" in body
    assert "status" in body
    assert body["status"] == response.status_code
    return body


def test_not_found_uses_problem_details(api_client) -> None:
    r = api_client.get(f"/api/boards/{_UNKNOWN_BOARD_ID}")
    assert r.status_code == 404
    body = _assert_problem_json(r)
    assert body["type"] == "about:blank"
    assert body["detail"] == "Board not found"
    assert str(api_client.base_url).rstrip("/") in body.get("instance", "")


def test_validation_error_includes_errors_array(api_client) -> None:
    r = api_client.post("/api/boards", json={"title": ""})
    assert r.status_code == 422
    body = _assert_problem_json(r)
    assert "errors" in body
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) >= 1


def test_application_validation_422_uses_problem_details(api_client) -> None:
    board = api_client.post("/api/boards", json={"title": "x"})
    assert board.status_code == 201
    board_id = board.json()["id"]
    col = api_client.post(f"/api/boards/{board_id}/columns", json={"title": "c"})
    assert col.status_code == 201
    card = api_client.post(
        f"/api/columns/{col.json()['id']}/cards",
        json={"title": "t", "description": None},
    )
    assert card.status_code == 201
    r = api_client.patch(f"/api/cards/{card.json()['id']}", json={})
    assert r.status_code == 422
    body = _assert_problem_json(r)
    assert "detail" in body
