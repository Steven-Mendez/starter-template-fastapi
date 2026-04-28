"""RFC 9457 Problem Details (application/problem+json) for API errors."""

from __future__ import annotations

from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

pytestmark = pytest.mark.integration

_UNKNOWN_BOARD_ID = "00000000-0000-4000-8000-000000000001"
_UNKNOWN_CARD_ID = "00000000-0000-4000-8000-000000000099"
_UNKNOWN_COLUMN_ID = "00000000-0000-4000-8000-000000000077"

_PROBLEM_BASE = "https://starter-template-fastapi.dev/problems"


def _assert_problem_json(response: Response) -> dict[str, Any]:
    ctype = response.headers.get("content-type", "")
    assert ctype.startswith("application/problem+json"), ctype
    body = response.json()
    assert "type" in body
    assert "title" in body
    assert "status" in body
    assert body["status"] == response.status_code
    return body


def test_not_found_uses_problem_details(api_client: TestClient) -> None:
    r = api_client.get(f"/api/boards/{_UNKNOWN_BOARD_ID}")
    assert r.status_code == 404
    body = _assert_problem_json(r)
    assert body["type"] == f"{_PROBLEM_BASE}/board-not-found"
    assert body["code"] == "board_not_found"
    assert body["detail"] == "Board not found"
    assert str(api_client.base_url).rstrip("/") in body.get("instance", "")


def test_validation_error_includes_errors_array(api_client: TestClient) -> None:
    r = api_client.post("/api/boards", json={"title": ""})
    assert r.status_code == 422
    body = _assert_problem_json(r)
    assert "errors" in body
    assert isinstance(body["errors"], list)
    assert len(body["errors"]) >= 1


def test_application_validation_422_uses_problem_details(
    api_client: TestClient,
) -> None:
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
    assert body["type"] == f"{_PROBLEM_BASE}/patch-no-changes"
    assert body["code"] == "patch_no_changes"
    assert body["detail"] == "At least one field must be provided"


@pytest.mark.parametrize(
    (
        "trigger",
        "expected_status",
        "expected_type",
        "expected_code",
        "expected_detail",
    ),
    [
        (
            lambda c: c.get(f"/api/boards/{_UNKNOWN_BOARD_ID}"),
            404,
            f"{_PROBLEM_BASE}/board-not-found",
            "board_not_found",
            "Board not found",
        ),
        (
            lambda c: c.get(f"/api/cards/{_UNKNOWN_CARD_ID}"),
            404,
            f"{_PROBLEM_BASE}/card-not-found",
            "card_not_found",
            "Card not found",
        ),
        (
            lambda c: c.post(
                f"/api/columns/{_UNKNOWN_COLUMN_ID}/cards",
                json={"title": "x", "description": None},
            ),
            404,
            f"{_PROBLEM_BASE}/column-not-found",
            "column_not_found",
            "Column not found",
        ),
    ],
)
def test_application_not_found_errors_expose_machine_readable_contract(
    api_client: TestClient,
    trigger: Any,
    expected_status: int,
    expected_type: str,
    expected_code: str,
    expected_detail: str,
) -> None:
    response = trigger(api_client)
    assert response.status_code == expected_status
    body = _assert_problem_json(response)
    assert body["type"] == expected_type
    assert body["code"] == expected_code
    assert body["detail"] == expected_detail


def test_invalid_card_move_exposes_conflict_problem_contract(
    api_client: TestClient,
) -> None:
    board_a = api_client.post("/api/boards", json={"title": "A"})
    board_b = api_client.post("/api/boards", json={"title": "B"})
    col_a = api_client.post(
        f"/api/boards/{board_a.json()['id']}/columns",
        json={"title": "A1"},
    )
    col_b = api_client.post(
        f"/api/boards/{board_b.json()['id']}/columns",
        json={"title": "B1"},
    )
    card = api_client.post(
        f"/api/columns/{col_a.json()['id']}/cards",
        json={"title": "Move me", "description": None},
    )
    response = api_client.patch(
        f"/api/cards/{card.json()['id']}",
        json={"column_id": col_b.json()["id"]},
    )
    assert response.status_code == 409
    body = _assert_problem_json(response)
    assert body["type"] == f"{_PROBLEM_BASE}/invalid-card-move"
    assert body["code"] == "invalid_card_move"
    assert body["detail"] == "Invalid card move"


def test_missing_dependency_container_returns_service_unavailable_problem(
    api_client: TestClient,
) -> None:
    app = cast(FastAPI, api_client.app)
    app.state.container = None

    response = api_client.get(f"/api/boards/{_UNKNOWN_BOARD_ID}")

    assert response.status_code == 503
    body = _assert_problem_json(response)
    assert body["type"] == f"{_PROBLEM_BASE}/service-unavailable"
    assert body["code"] == "dependency_container_not_ready"
    assert body["detail"] == "Application container is not initialized in lifespan"
