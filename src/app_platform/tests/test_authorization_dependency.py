"""Unit tests for the platform-level ``require_authorization`` dependency."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.authorization import require_authorization
from app_platform.api.dependencies.container import set_app_container
from app_platform.config.settings import AppSettings
from app_platform.shared.principal import Principal
from app_platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


_PRINCIPAL = Principal(
    user_id=uuid4(),
    email="user@example.com",
    is_active=True,
    is_verified=True,
    authz_version=1,
)


class _FakeAuthorization:
    def __init__(self, *, allow: bool) -> None:
        self.allow = allow
        self.last_call: tuple[UUID, str, str, str] | None = None

    def check(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        self.last_call = (user_id, action, resource_type, resource_id)
        return self.allow


def _resolver(token: str):  # type: ignore[no-untyped-def]
    if token == "valid":
        return Ok(_PRINCIPAL)
    return Err(RuntimeError("invalid"))


def _make_app(authz: _FakeAuthorization) -> FastAPI:
    settings = AppSettings(
        environment="test",
        auth_jwt_secret_key="test-secret-key-with-at-least-32-bytes",
        auth_redis_url=None,
    )
    app = build_fastapi_app(settings)

    @app.get(
        "/board/{board_id}",
        dependencies=[
            require_authorization(
                "read",
                "thing",
                lambda r: r.path_params["board_id"],
            )
        ],
    )
    def _read_board(board_id: str) -> dict[str, str]:
        return {"id": board_id}

    @app.get(
        "/admin",
        dependencies=[require_authorization("manage_users", "system", None)],
    )
    def _admin() -> dict[str, str]:
        return {"ok": "yes"}

    @asynccontextmanager
    async def lifespan(a: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(a, type("C", (), {"settings": settings})())
        a.state.principal_resolver = _resolver
        a.state.authorization = authz
        yield

    app.router.lifespan_context = lifespan
    return app


@pytest.fixture
def allow_client() -> Iterator[TestClient]:
    authz = _FakeAuthorization(allow=True)
    with TestClient(_make_app(authz)) as client:
        client.headers["Authorization"] = "Bearer valid"
        yield client


@pytest.fixture
def deny_client() -> Iterator[tuple[TestClient, _FakeAuthorization]]:
    authz = _FakeAuthorization(allow=False)
    with TestClient(_make_app(authz)) as client:
        client.headers["Authorization"] = "Bearer valid"
        yield client, authz


def test_allow_passes_through_to_handler(allow_client: TestClient) -> None:
    resp = allow_client.get("/board/abc")
    assert resp.status_code == 200
    assert resp.json() == {"id": "abc"}


def test_deny_returns_403(
    deny_client: tuple[TestClient, _FakeAuthorization],
) -> None:
    client, _ = deny_client
    resp = client.get("/board/abc")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Permission denied"


def test_id_loader_extracts_path_param(
    deny_client: tuple[TestClient, _FakeAuthorization],
) -> None:
    client, authz = deny_client
    client.get("/board/board-42")
    assert authz.last_call is not None
    assert authz.last_call[1:] == ("read", "thing", "board-42")


def test_no_id_loader_uses_main_sentinel(
    deny_client: tuple[TestClient, _FakeAuthorization],
) -> None:
    client, authz = deny_client
    client.get("/admin")
    assert authz.last_call is not None
    assert authz.last_call[1:] == ("manage_users", "system", "main")


def test_missing_credentials_return_401(allow_client: TestClient) -> None:
    allow_client.headers.pop("Authorization", None)
    resp = allow_client.get("/board/abc")
    assert resp.status_code == 401


def test_invalid_credentials_return_401(allow_client: TestClient) -> None:
    allow_client.headers["Authorization"] = "Bearer wrong"
    resp = allow_client.get("/board/abc")
    assert resp.status_code == 401
