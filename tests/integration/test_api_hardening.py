from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.config.settings import AppSettings
from src.main import create_app

pytestmark = pytest.mark.integration


def test_docs_can_be_disabled_by_settings() -> None:
    app = create_app(AppSettings(enable_docs=False))
    with TestClient(app) as client:
        response = client.get("/docs")
    assert response.status_code == 404


def test_cors_preflight_allows_configured_origin() -> None:
    app = create_app(
        AppSettings(
            cors_origins=["https://frontend.example.com"],
            trusted_hosts=["testserver"],
        )
    )
    with TestClient(app) as client:
        response = client.options(
            "/health",
            headers={
                "Origin": "https://frontend.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "https://frontend.example.com"
    )


def test_trusted_host_rejects_unknown_host_on_production() -> None:
    app = create_app(
        AppSettings(
            environment="production",
            trusted_hosts=["api.example.com"],
        )
    )
    with TestClient(app, base_url="http://untrusted.example.org") as client:
        response = client.get("/health")
    assert response.status_code == 400


def test_problem_details_includes_request_id_extension(
    api_client: TestClient,
) -> None:
    response = api_client.get(
        "/api/boards/00000000-0000-4000-8000-000000000001",
        headers={"X-Request-ID": "req-123"},
    )
    assert response.status_code == 404
    assert response.headers["x-request-id"] == "req-123"
    assert response.json()["request_id"] == "req-123"


def test_invalid_card_move_returns_conflict(api_client: TestClient) -> None:
    board_a = api_client.post("/api/boards", json={"title": "A"})
    board_b = api_client.post("/api/boards", json={"title": "B"})
    col_a = api_client.post(
        f"/api/boards/{board_a.json()['id']}/columns", json={"title": "A1"}
    )
    col_b = api_client.post(
        f"/api/boards/{board_b.json()['id']}/columns", json={"title": "B1"}
    )
    card = api_client.post(
        f"/api/columns/{col_a.json()['id']}/cards",
        json={"title": "Move me", "description": None},
    )
    move = api_client.patch(
        f"/api/cards/{card.json()['id']}",
        json={"column_id": col_b.json()["id"]},
    )
    assert move.status_code == 409
