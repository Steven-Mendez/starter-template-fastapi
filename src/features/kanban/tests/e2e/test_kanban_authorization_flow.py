"""End-to-end ReBAC flow over the kanban surface.

The fixtures grant relationships in-process via ``FakeAuthorization`` so
we can exercise route gating, hierarchy, and listing without spinning
up a real auth backend. The real engine has its own unit and integration
suites under ``src/features/auth/tests/``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.features.authorization.application.types import Relationship
from src.features.kanban.tests.e2e.conftest import (
    _READ_ONLY_PRINCIPAL,
    FakeAuthorization,
)

pytestmark = pytest.mark.e2e


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


def test_creator_owns_the_board_and_can_read_update_delete(
    client: TestClient,
) -> None:
    create = client.post("/api/boards", json={"title": "Owned"})
    assert create.status_code == 201
    board_id = create.json()["id"]

    # Read.
    assert client.get(f"/api/boards/{board_id}").status_code == 200
    # Update.
    assert (
        client.patch(f"/api/boards/{board_id}", json={"title": "Renamed"}).status_code
        == 200
    )
    # Delete.
    assert client.delete(f"/api/boards/{board_id}").status_code == 204


def test_writer_can_update_but_not_delete(
    client: TestClient, read_only_client: TestClient, authorization: FakeAuthorization
) -> None:
    create = client.post("/api/boards", json={"title": "Shared"})
    board_id = create.json()["id"]

    _grant(
        authorization,
        board_id=board_id,
        relation="writer",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )

    assert read_only_client.get(f"/api/boards/{board_id}").status_code == 200
    assert (
        read_only_client.patch(
            f"/api/boards/{board_id}", json={"title": "Other"}
        ).status_code
        == 200
    )
    assert read_only_client.delete(f"/api/boards/{board_id}").status_code == 403


def test_reader_can_only_read(
    client: TestClient, read_only_client: TestClient, authorization: FakeAuthorization
) -> None:
    board_id = client.post("/api/boards", json={"title": "Read-only"}).json()["id"]

    _grant(
        authorization,
        board_id=board_id,
        relation="reader",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )

    assert read_only_client.get(f"/api/boards/{board_id}").status_code == 200
    assert (
        read_only_client.patch(
            f"/api/boards/{board_id}", json={"title": "Nope"}
        ).status_code
        == 403
    )
    assert read_only_client.delete(f"/api/boards/{board_id}").status_code == 403


def test_non_member_gets_403_on_every_action(
    client: TestClient, read_only_client: TestClient
) -> None:
    board_id = client.post("/api/boards", json={"title": "Private"}).json()["id"]

    assert read_only_client.get(f"/api/boards/{board_id}").status_code == 403
    assert (
        read_only_client.patch(
            f"/api/boards/{board_id}", json={"title": "Hijack"}
        ).status_code
        == 403
    )
    assert read_only_client.delete(f"/api/boards/{board_id}").status_code == 403


def test_list_boards_filters_by_authorization(
    client: TestClient, read_only_client: TestClient, authorization: FakeAuthorization
) -> None:
    a_id = client.post("/api/boards", json={"title": "A"}).json()["id"]
    b_id = client.post("/api/boards", json={"title": "B"}).json()["id"]
    c_id = client.post("/api/boards", json={"title": "C"}).json()["id"]

    # Grant the read-only user reader on B only.
    _grant(
        authorization,
        board_id=b_id,
        relation="reader",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )

    creator_list = client.get("/api/boards")
    assert creator_list.status_code == 200
    assert {b["id"] for b in creator_list.json()} == {a_id, b_id, c_id}

    reader_list = read_only_client.get("/api/boards")
    assert reader_list.status_code == 200
    assert [b["id"] for b in reader_list.json()] == [b_id]


def test_owner_grant_unlocks_delete_for_writer(
    client: TestClient, read_only_client: TestClient, authorization: FakeAuthorization
) -> None:
    """Promoting writer → owner should make delete succeed without re-login."""
    board_id = client.post("/api/boards", json={"title": "Promote"}).json()["id"]
    _grant(
        authorization,
        board_id=board_id,
        relation="writer",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )
    assert read_only_client.delete(f"/api/boards/{board_id}").status_code == 403

    _grant(
        authorization,
        board_id=board_id,
        relation="owner",
        user_id=str(_READ_ONLY_PRINCIPAL.user_id),
    )
    assert read_only_client.delete(f"/api/boards/{board_id}").status_code == 204


def test_anonymous_request_is_rejected_with_401(
    unauthenticated_client: TestClient,
) -> None:
    assert unauthenticated_client.get("/api/boards").status_code == 401
    assert (
        unauthenticated_client.post("/api/boards", json={"title": "Nope"}).status_code
        == 401
    )
