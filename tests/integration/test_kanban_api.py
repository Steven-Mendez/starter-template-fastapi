from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.integration

_ISO_DUE = "2030-07-20T14:30:00+00:00"
_WHEN = datetime(2030, 7, 20, 14, 30, tzinfo=timezone.utc)

_UNKNOWN_BOARD_ID = "00000000-0000-4000-8000-000000000001"
_UNKNOWN_CARD_ID = "00000000-0000-4000-8000-000000000099"


def test_post_card_default_and_explicit_priority_and_patch(api_client) -> None:
    board = api_client.post("/api/boards", json={"title": "P"})
    assert board.status_code == 201
    board_id = board.json()["id"]
    col = api_client.post(f"/api/boards/{board_id}/columns", json={"title": "Todo"})
    assert col.status_code == 201
    col_id = col.json()["id"]

    default_card = api_client.post(
        f"/api/columns/{col_id}/cards",
        json={"title": "d", "description": None},
    )
    assert default_card.status_code == 201
    assert default_card.json()["priority"] == "medium"

    high_card = api_client.post(
        f"/api/columns/{col_id}/cards",
        json={"title": "h", "description": None, "priority": "high"},
    )
    assert high_card.status_code == 201
    cid = high_card.json()["id"]
    assert high_card.json()["priority"] == "high"

    patched = api_client.patch(f"/api/cards/{cid}", json={"priority": "low"})
    assert patched.status_code == 200
    assert patched.json()["priority"] == "low"


def test_create_card_rejects_invalid_priority(api_client) -> None:
    board = api_client.post("/api/boards", json={"title": "bad-prio"})
    assert board.status_code == 201
    col = api_client.post(
        f"/api/boards/{board.json()['id']}/columns", json={"title": "c"}
    )
    assert col.status_code == 201
    r = api_client.post(
        f"/api/columns/{col.json()['id']}/cards",
        json={"title": "t", "description": None, "priority": "urgent"},
    )
    assert r.status_code == 422


def test_post_card_due_at_and_patch_clear(api_client) -> None:
    board = api_client.post("/api/boards", json={"title": "Due"})
    assert board.status_code == 201
    board_id = board.json()["id"]
    col = api_client.post(f"/api/boards/{board_id}/columns", json={"title": "Todo"})
    assert col.status_code == 201
    col_id = col.json()["id"]

    default_card = api_client.post(
        f"/api/columns/{col_id}/cards",
        json={"title": "no due", "description": None},
    )
    assert default_card.status_code == 201
    assert default_card.json()["due_at"] is None

    with_due = api_client.post(
        f"/api/columns/{col_id}/cards",
        json={
            "title": "due",
            "description": None,
            "due_at": _ISO_DUE,
        },
    )
    assert with_due.status_code == 201
    cid = with_due.json()["id"]
    body = with_due.json()
    assert datetime.fromisoformat(body["due_at"]) == _WHEN

    patched = api_client.patch(f"/api/cards/{cid}", json={"due_at": None})
    assert patched.status_code == 200
    assert patched.json()["due_at"] is None

    set_again = api_client.patch(
        f"/api/cards/{cid}", json={"due_at": _ISO_DUE}
    )
    assert set_again.status_code == 200
    assert datetime.fromisoformat(set_again.json()["due_at"]) == _WHEN


def test_patch_due_at_only_is_valid(api_client) -> None:
    board = api_client.post("/api/boards", json={"title": "x"})
    assert board.status_code == 201
    col = api_client.post(
        f"/api/boards/{board.json()['id']}/columns", json={"title": "c"}
    )
    assert col.status_code == 201
    card = api_client.post(
        f"/api/columns/{col.json()['id']}/cards",
        json={"title": "t", "description": None},
    )
    assert card.status_code == 201
    cid = card.json()["id"]
    r = api_client.patch(f"/api/cards/{cid}", json={"due_at": _ISO_DUE})
    assert r.status_code == 200
    assert datetime.fromisoformat(r.json()["due_at"]) == _WHEN


def test_get_board_includes_due_at_on_nested_cards(api_client) -> None:
    board = api_client.post("/api/boards", json={"title": "Due nested"})
    assert board.status_code == 201
    board_id = board.json()["id"]
    col = api_client.post(f"/api/boards/{board_id}/columns", json={"title": "c"})
    assert col.status_code == 201
    col_id = col.json()["id"]
    api_client.post(
        f"/api/columns/{col_id}/cards",
        json={"title": "x", "description": None, "due_at": _ISO_DUE},
    )
    detail = api_client.get(f"/api/boards/{board_id}").json()
    assert datetime.fromisoformat(
        detail["columns"][0]["cards"][0]["due_at"]
    ) == _WHEN


def test_get_board_includes_priority_on_nested_cards(api_client) -> None:
    board = api_client.post("/api/boards", json={"title": "P"})
    assert board.status_code == 201
    board_id = board.json()["id"]
    col = api_client.post(f"/api/boards/{board_id}/columns", json={"title": "c"})
    assert col.status_code == 201
    col_id = col.json()["id"]
    api_client.post(
        f"/api/columns/{col_id}/cards",
        json={"title": "x", "description": None, "priority": "high"},
    )
    detail = api_client.get(f"/api/boards/{board_id}").json()
    assert detail["columns"][0]["cards"][0]["priority"] == "high"


def test_create_board_columns_card_move_and_read_detail(api_client) -> None:
    board_resp = api_client.post("/api/boards", json={"title": "Sprint"})
    assert board_resp.status_code == 201
    board_id = board_resp.json()["id"]

    todo_resp = api_client.post(f"/api/boards/{board_id}/columns", json={"title": "Todo"})
    done_resp = api_client.post(f"/api/boards/{board_id}/columns", json={"title": "Done"})
    assert todo_resp.status_code == 201 and done_resp.status_code == 201
    todo_id = todo_resp.json()["id"]
    done_id = done_resp.json()["id"]

    card_resp = api_client.post(
        f"/api/columns/{todo_id}/cards",
        json={"title": "Task", "description": None},
    )
    assert card_resp.status_code == 201
    card_id = card_resp.json()["id"]

    move_resp = api_client.patch(
        f"/api/cards/{card_id}",
        json={"column_id": done_id, "title": "Done"},
    )
    assert move_resp.status_code == 200

    detail = api_client.get(f"/api/boards/{board_id}").json()
    by_title = {col["title"]: col for col in detail["columns"]}
    assert len(by_title["Todo"]["cards"]) == 0
    assert len(by_title["Done"]["cards"]) == 1
    assert by_title["Done"]["cards"][0]["title"] == "Done"


def test_patch_without_fields_returns_422(api_client) -> None:
    board = api_client.post("/api/boards", json={"title": "x"})
    assert board.status_code == 201
    board_id = board.json()["id"]
    assert api_client.patch(f"/api/boards/{board_id}", json={}).status_code == 422

    col = api_client.post(f"/api/boards/{board_id}/columns", json={"title": "c"})
    assert col.status_code == 201
    card = api_client.post(
        f"/api/columns/{col.json()['id']}/cards",
        json={"title": "t", "description": None},
    )
    assert card.status_code == 201
    assert api_client.patch(f"/api/cards/{card.json()['id']}", json={}).status_code == 422


def test_unknown_board_or_card_returns_not_found(api_client) -> None:
    assert api_client.get(f"/api/boards/{_UNKNOWN_BOARD_ID}").status_code == 404
    assert api_client.get(f"/api/cards/{_UNKNOWN_CARD_ID}").status_code == 404


def test_empty_board_title_is_rejected(api_client) -> None:
    assert api_client.post("/api/boards", json={"title": ""}).status_code == 422


def test_create_and_delete_board_use_expected_http_semantics(api_client) -> None:
    response = api_client.post("/api/boards", json={"title": "Lifecycle"})
    assert response.status_code == 201
    board_id = response.json()["id"]
    assert api_client.delete(f"/api/boards/{board_id}").status_code == 204
    assert api_client.get(f"/api/boards/{board_id}").status_code == 404
