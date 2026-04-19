from __future__ import annotations

from datetime import datetime, timezone
from typing import cast

import pytest
from fastapi.testclient import TestClient

from tests.support.kanban_builders import ApiBuilder, JsonDict, require_str

pytestmark = pytest.mark.integration

_ISO_DUE = "2030-07-20T14:30:00+00:00"
_WHEN = datetime(2030, 7, 20, 14, 30, tzinfo=timezone.utc)

_UNKNOWN_BOARD_ID = "00000000-0000-4000-8000-000000000001"
_UNKNOWN_CARD_ID = "00000000-0000-4000-8000-000000000099"


def _json_list(value: object) -> list[JsonDict]:
    assert isinstance(value, list)
    return [cast(JsonDict, item) for item in value if isinstance(item, dict)]


def _columns_by_title(detail: JsonDict) -> dict[str, JsonDict]:
    columns = _json_list(detail.get("columns"))
    return {require_str(column, "title"): column for column in columns}


def _find_card(detail: JsonDict, card_id: str) -> JsonDict:
    for column in _json_list(detail.get("columns")):
        for card in _json_list(column.get("cards")):
            if require_str(card, "id") == card_id:
                return card
    raise AssertionError(f"Card {card_id} was not found in board detail")


def test_post_card_default_and_explicit_priority_and_patch(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("P")
    col_id = api_kanban.column_id(board_id, "Todo")

    default_card = api_kanban.card(col_id, "d")
    assert default_card["priority"] == "medium"

    high_card = api_kanban.card(col_id, "h", priority="high")
    cid = require_str(high_card, "id")
    assert high_card["priority"] == "high"

    patched = api_client.patch(f"/api/cards/{cid}", json={"priority": "low"})
    assert patched.status_code == 200
    assert patched.json()["priority"] == "low"


def test_create_card_rejects_invalid_priority(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("bad-prio")
    col_id = api_kanban.column_id(board_id, "c")
    response = api_client.post(
        f"/api/columns/{col_id}/cards",
        json={"title": "t", "description": None, "priority": "urgent"},
    )
    assert response.status_code == 422


def test_post_card_due_at_and_patch_clear(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("Due")
    col_id = api_kanban.column_id(board_id, "Todo")

    default_card = api_kanban.card(col_id, "no due")
    assert default_card["due_at"] is None

    with_due = api_kanban.card(col_id, "due", due_at=_ISO_DUE)
    cid = require_str(with_due, "id")
    assert datetime.fromisoformat(require_str(with_due, "due_at")) == _WHEN

    patched = api_client.patch(f"/api/cards/{cid}", json={"due_at": None})
    assert patched.status_code == 200
    assert patched.json()["due_at"] is None

    set_again = api_client.patch(f"/api/cards/{cid}", json={"due_at": _ISO_DUE})
    assert set_again.status_code == 200
    assert datetime.fromisoformat(set_again.json()["due_at"]) == _WHEN


def test_patch_due_at_only_is_valid(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("x")
    col_id = api_kanban.column_id(board_id, "c")
    card_id = api_kanban.card_id(col_id, "t")

    response = api_client.patch(f"/api/cards/{card_id}", json={"due_at": _ISO_DUE})
    assert response.status_code == 200
    assert datetime.fromisoformat(response.json()["due_at"]) == _WHEN


def test_get_board_includes_due_at_on_nested_cards(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("Due nested")
    col_id = api_kanban.column_id(board_id, "c")
    card = api_kanban.card(col_id, "x", due_at=_ISO_DUE)
    card_id = require_str(card, "id")

    detail = cast(JsonDict, api_client.get(f"/api/boards/{board_id}").json())
    nested_card = _find_card(detail, card_id)
    assert datetime.fromisoformat(require_str(nested_card, "due_at")) == _WHEN


def test_get_board_includes_priority_on_nested_cards(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("P")
    col_id = api_kanban.column_id(board_id, "c")
    card = api_kanban.card(col_id, "x", priority="high")
    card_id = require_str(card, "id")

    detail = cast(JsonDict, api_client.get(f"/api/boards/{board_id}").json())
    nested_card = _find_card(detail, card_id)
    assert nested_card["priority"] == "high"


def test_create_board_columns_card_move_and_read_detail(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("Sprint")
    todo_id = api_kanban.column_id(board_id, "Todo")
    done_id = api_kanban.column_id(board_id, "Done")
    card_id = api_kanban.card_id(todo_id, "Task")

    move_resp = api_client.patch(
        f"/api/cards/{card_id}",
        json={"column_id": done_id, "title": "Done"},
    )
    assert move_resp.status_code == 200

    detail = cast(JsonDict, api_client.get(f"/api/boards/{board_id}").json())
    by_title = _columns_by_title(detail)
    todo_cards = _json_list(by_title["Todo"].get("cards"))
    done_cards = _json_list(by_title["Done"].get("cards"))
    assert len(todo_cards) == 0
    assert len(done_cards) == 1
    assert done_cards[0]["title"] == "Done"


def test_patch_without_fields_returns_422(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("x")
    assert api_client.patch(f"/api/boards/{board_id}", json={}).status_code == 422

    col_id = api_kanban.column_id(board_id, "c")
    card_id = api_kanban.card_id(col_id, "t")
    assert api_client.patch(f"/api/cards/{card_id}", json={}).status_code == 422


def test_unknown_board_or_card_returns_not_found(api_client: TestClient) -> None:
    assert api_client.get(f"/api/boards/{_UNKNOWN_BOARD_ID}").status_code == 404
    assert api_client.get(f"/api/cards/{_UNKNOWN_CARD_ID}").status_code == 404


def test_empty_board_title_is_rejected(api_client: TestClient) -> None:
    assert api_client.post("/api/boards", json={"title": ""}).status_code == 422


def test_create_and_delete_board_use_expected_http_semantics(
    api_client: TestClient,
    api_kanban: ApiBuilder,
) -> None:
    board_id = api_kanban.board_id("Lifecycle")
    assert api_client.delete(f"/api/boards/{board_id}").status_code == 204
    assert api_client.get(f"/api/boards/{board_id}").status_code == 404
