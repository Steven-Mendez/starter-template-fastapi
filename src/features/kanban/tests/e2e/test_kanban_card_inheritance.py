"""End-to-end tests for cross-resource ReBAC inheritance over the kanban surface.

The fake authorization adapter walks card → column → board via the
in-memory kanban repository, mirroring the real engine's parent-walk
logic. These tests confirm that granting a board-level relation extends
to every column and card under that board through the HTTP layer.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.features.auth.application.authorization.types import Relationship
from src.features.kanban.tests.e2e.conftest import (
    _READ_ONLY_PRINCIPAL,
    FakeAuthorization,
)

pytestmark = pytest.mark.e2e


def _seed_card(client: TestClient) -> tuple[str, str, str]:
    """Create a board, a column on it, and a card on that column."""
    board_id = client.post("/api/boards", json={"title": "Inherit"}).json()["id"]
    column_id = client.post(
        f"/api/boards/{board_id}/columns", json={"title": "Doing"}
    ).json()["id"]
    card_id = client.post(
        f"/api/columns/{column_id}/cards", json={"title": "Task"}
    ).json()["id"]
    return board_id, column_id, card_id


def _grant(
    authz: FakeAuthorization, *, board_id: str, relation: str, user_id: str
) -> None:
    authz.grant(
        Relationship(
            resource_type="kanban",
            resource_id=board_id,
            relation=relation,
            subject_type="user",
            subject_id=user_id,
        )
    )


def test_board_reader_can_get_card(
    client: TestClient,
    read_only_client: TestClient,
    authorization: FakeAuthorization,
) -> None:
    board_id, _, card_id = _seed_card(client)
    _grant(
        authorization,
        board_id=board_id,
        relation="reader",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )

    response = read_only_client.get(f"/api/cards/{card_id}")
    assert response.status_code == 200


def test_board_writer_can_patch_card(
    client: TestClient,
    read_only_client: TestClient,
    authorization: FakeAuthorization,
) -> None:
    board_id, _, card_id = _seed_card(client)
    _grant(
        authorization,
        board_id=board_id,
        relation="writer",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )

    response = read_only_client.patch(
        f"/api/cards/{card_id}", json={"title": "Updated"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"


def test_board_reader_cannot_patch_card(
    client: TestClient,
    read_only_client: TestClient,
    authorization: FakeAuthorization,
) -> None:
    board_id, _, card_id = _seed_card(client)
    _grant(
        authorization,
        board_id=board_id,
        relation="reader",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )

    response = read_only_client.patch(f"/api/cards/{card_id}", json={"title": "Nope"})
    assert response.status_code == 403


def test_non_member_gets_403_on_card_routes(
    client: TestClient,
    read_only_client: TestClient,
) -> None:
    """No grant on the parent board → card routes deny."""
    _, _, card_id = _seed_card(client)
    assert read_only_client.get(f"/api/cards/{card_id}").status_code == 403
    assert (
        read_only_client.patch(f"/api/cards/{card_id}", json={"title": "x"}).status_code
        == 403
    )


def test_board_writer_can_create_card_in_column(
    client: TestClient,
    read_only_client: TestClient,
    authorization: FakeAuthorization,
) -> None:
    board_id = client.post("/api/boards", json={"title": "Shared"}).json()["id"]
    column_id = client.post(
        f"/api/boards/{board_id}/columns", json={"title": "TODO"}
    ).json()["id"]

    _grant(
        authorization,
        board_id=board_id,
        relation="writer",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )

    response = read_only_client.post(
        f"/api/columns/{column_id}/cards", json={"title": "Hello"}
    )
    assert response.status_code == 201


def test_board_reader_cannot_create_card_in_column(
    client: TestClient,
    read_only_client: TestClient,
    authorization: FakeAuthorization,
) -> None:
    board_id = client.post("/api/boards", json={"title": "Shared"}).json()["id"]
    column_id = client.post(
        f"/api/boards/{board_id}/columns", json={"title": "TODO"}
    ).json()["id"]

    _grant(
        authorization,
        board_id=board_id,
        relation="reader",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )

    response = read_only_client.post(
        f"/api/columns/{column_id}/cards", json={"title": "Hello"}
    )
    assert response.status_code == 403
