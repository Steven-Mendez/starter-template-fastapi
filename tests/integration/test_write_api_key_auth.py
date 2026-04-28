from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

_WRITE_API_KEY = "integration-write-api-key"


def _auth_headers(api_key: str = _WRITE_API_KEY) -> dict[str, str]:
    return {"X-API-Key": api_key}


def test_mutating_routes_reject_missing_api_key(
    api_client_with_write_key: TestClient,
) -> None:
    board_id = api_client_with_write_key.post(
        "/api/boards",
        json={"title": "Protected"},
        headers=_auth_headers(),
    ).json()["id"]
    column_id = api_client_with_write_key.post(
        f"/api/boards/{board_id}/columns",
        json={"title": "Todo"},
        headers=_auth_headers(),
    ).json()["id"]
    card_id = api_client_with_write_key.post(
        f"/api/columns/{column_id}/cards",
        json={"title": "Task"},
        headers=_auth_headers(),
    ).json()["id"]

    mutating_requests: list[tuple[str, str, dict[str, str] | None]] = [
        ("post", "/api/boards", {"title": "No auth"}),
        ("patch", f"/api/boards/{board_id}", {"title": "No auth"}),
        ("delete", f"/api/boards/{board_id}", None),
        ("post", f"/api/boards/{board_id}/columns", {"title": "No auth"}),
        ("delete", f"/api/columns/{column_id}", None),
        ("post", f"/api/columns/{column_id}/cards", {"title": "No auth"}),
        ("patch", f"/api/cards/{card_id}", {"title": "No auth"}),
    ]

    for method, path, body in mutating_requests:
        request = getattr(api_client_with_write_key, method)
        if body is None:
            response = request(path)
        else:
            response = request(path, json=body)
        assert response.status_code == 401


def test_mutating_routes_reject_incorrect_api_key(
    api_client_with_write_key: TestClient,
) -> None:
    board_response = api_client_with_write_key.post(
        "/api/boards",
        json={"title": "Protected"},
        headers=_auth_headers(),
    )
    board_id = board_response.json()["id"]

    headers = _auth_headers("not-correct")
    assert (
        api_client_with_write_key.post(
            "/api/boards", json={"title": "Blocked"}, headers=headers
        ).status_code
        == 401
    )
    assert (
        api_client_with_write_key.patch(
            f"/api/boards/{board_id}", json={"title": "Blocked"}, headers=headers
        ).status_code
        == 401
    )
    assert (
        api_client_with_write_key.delete(
            f"/api/boards/{board_id}", headers=headers
        ).status_code
        == 401
    )


def test_mutating_routes_allow_correct_api_key(
    api_client_with_write_key: TestClient,
) -> None:
    headers = _auth_headers()
    create_board = api_client_with_write_key.post(
        "/api/boards", json={"title": "Allowed"}, headers=headers
    )
    assert create_board.status_code == 201
    board_id = create_board.json()["id"]

    update_board = api_client_with_write_key.patch(
        f"/api/boards/{board_id}",
        json={"title": "Allowed renamed"},
        headers=headers,
    )
    assert update_board.status_code == 200

    delete_board = api_client_with_write_key.delete(
        f"/api/boards/{board_id}",
        headers=headers,
    )
    assert delete_board.status_code == 204


def test_read_routes_remain_accessible_without_api_key(
    api_client_with_write_key: TestClient,
) -> None:
    create_board = api_client_with_write_key.post(
        "/api/boards",
        json={"title": "Read route"},
        headers=_auth_headers(),
    )
    board_id = create_board.json()["id"]

    list_boards = api_client_with_write_key.get("/api/boards")
    assert list_boards.status_code == 200
    assert any(board["id"] == board_id for board in list_boards.json())

    get_board = api_client_with_write_key.get(f"/api/boards/{board_id}")
    assert get_board.status_code == 200
