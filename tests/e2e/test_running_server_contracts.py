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
