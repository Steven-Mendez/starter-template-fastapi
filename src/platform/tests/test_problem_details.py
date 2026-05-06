"""End-to-end coverage for the RFC 9457 Problem Details error responses."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.platform.api.app_factory import build_fastapi_app
from src.platform.api.dependencies.container import (
    DependencyContainerNotReadyError,
    set_app_container,
)
from src.platform.api.error_handlers_app_exception import ApplicationHTTPException
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


@dataclass(frozen=True, slots=True)
class _Container:
    settings: AppSettings


def _build(settings: AppSettings, *, container: bool = True) -> FastAPI:
    app = build_fastapi_app(settings)

    @app.get("/__boom_application")
    def _boom_app() -> dict[str, str]:
        raise ApplicationHTTPException(
            status_code=409,
            detail="Conflict happened",
            code="custom_code",
            type_uri="https://example.test/problems/custom",
        )

    @app.get("/__boom_unhandled")
    def _boom_unhandled() -> dict[str, str]:
        raise RuntimeError("kaboom")

    @app.get("/__needs_container")
    def _needs_container() -> dict[str, str]:
        raise DependencyContainerNotReadyError("nope")

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        if container:
            set_app_container(lifespan_app, _Container(settings=settings))
        yield
        lifespan_app.state.container = None

    app.router.lifespan_context = lifespan
    return app


@pytest.fixture
def client(test_settings: AppSettings) -> Iterator[TestClient]:
    with TestClient(_build(test_settings)) as c:
        yield c


def test_application_http_exception(client: TestClient) -> None:
    resp = client.get("/__boom_application")
    assert resp.status_code == 409
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["status"] == 409
    assert body["detail"] == "Conflict happened"
    assert body["code"] == "custom_code"
    assert body["type"] == "https://example.test/problems/custom"
    assert "request_id" in body
    assert body["instance"].endswith("/__boom_application")


def test_unhandled_exception_returns_500(
    test_settings: AppSettings,
) -> None:
    with TestClient(_build(test_settings), raise_server_exceptions=False) as client:
        resp = client.get("/__boom_unhandled")
    assert resp.status_code == 500
    assert resp.headers["content-type"] == "application/problem+json"
    body = resp.json()
    assert body["status"] == 500
    assert body["title"] == "Internal Server Error"


def test_dependency_container_not_ready(
    test_settings: AppSettings,
) -> None:
    with TestClient(_build(test_settings, container=False)) as client:
        resp = client.get("/__needs_container")
    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "dependency_container_not_ready"
