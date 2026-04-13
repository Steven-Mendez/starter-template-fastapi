from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.e2e


def test_health_endpoint_on_running_server(api_base_url: str) -> None:
    response = httpx.get(f"{api_base_url}/health", timeout=10.0)
    assert response.status_code == 200
    assert response.json().get("status") == "ok"


def test_list_boards_on_fresh_server_returns_empty_list(api_base_url: str) -> None:
    response = httpx.get(f"{api_base_url}/api/boards", timeout=10.0)
    assert response.status_code == 200
    assert response.json() == []


def test_running_server_card_defaults_priority_medium(api_base_url: str) -> None:
    board = httpx.post(
        f"{api_base_url}/api/boards", json={"title": "E2E prio"}, timeout=10.0
    )
    assert board.status_code == 201
    bid = board.json()["id"]
    col = httpx.post(
        f"{api_base_url}/api/boards/{bid}/columns",
        json={"title": "Todo"},
        timeout=10.0,
    )
    assert col.status_code == 201
    cid = col.json()["id"]
    card = httpx.post(
        f"{api_base_url}/api/columns/{cid}/cards",
        json={"title": "task", "description": None},
        timeout=10.0,
    )
    assert card.status_code == 201
    assert card.json()["priority"] == "medium"


def test_running_server_patch_card_priority(api_base_url: str) -> None:
    board = httpx.post(
        f"{api_base_url}/api/boards", json={"title": "E2E patch"}, timeout=10.0
    )
    assert board.status_code == 201
    bid = board.json()["id"]
    col = httpx.post(
        f"{api_base_url}/api/boards/{bid}/columns",
        json={"title": "Col"},
        timeout=10.0,
    )
    assert col.status_code == 201
    col_id = col.json()["id"]
    card = httpx.post(
        f"{api_base_url}/api/columns/{col_id}/cards",
        json={"title": "t", "description": None, "priority": "high"},
        timeout=10.0,
    )
    assert card.status_code == 201
    card_id = card.json()["id"]
    patched = httpx.patch(
        f"{api_base_url}/api/cards/{card_id}",
        json={"priority": "low"},
        timeout=10.0,
    )
    assert patched.status_code == 200
    assert patched.json()["priority"] == "low"
