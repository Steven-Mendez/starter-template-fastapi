"""End-to-end coverage for the RFC 9457 Problem Details error responses."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, EmailStr

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.dependencies.container import (
    DependencyContainerNotReadyError,
    set_app_container,
)
from app_platform.api.error_handlers_app_exception import ApplicationHTTPException
from app_platform.config.settings import AppSettings

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


class _SingleFieldBody(BaseModel):
    value: int


class _TwoFieldBody(BaseModel):
    email: EmailStr
    name: str


class _NestedAddress(BaseModel):
    zip: int


class _NestedOuter(BaseModel):
    address: _NestedAddress


def _build_with_validate_endpoint(settings: AppSettings) -> FastAPI:
    app = build_fastapi_app(settings)

    @app.post("/__validate")
    def _validate(body: _SingleFieldBody) -> dict[str, int]:
        return {"value": body.value}

    return app


def _build_two_field_validate_endpoint(settings: AppSettings) -> FastAPI:
    """Endpoint that produces TWO distinct validation failures.

    Used to assert the ``violations`` array shape across environments.
    """
    app = build_fastapi_app(settings)

    @app.post("/__validate_two")
    def _validate(body: _TwoFieldBody) -> dict[str, str]:
        return {"email": body.email, "name": body.name}

    return app


def test_validation_error_in_development_returns_field_details(
    test_settings: AppSettings,
) -> None:
    dev_settings = test_settings.model_copy(update={"environment": "development"})
    with TestClient(_build_with_validate_endpoint(dev_settings)) as c:
        resp = c.post("/__validate", json={"value": "not-an-int"})
    assert resp.status_code == 422
    body = resp.json()
    assert "violations" in body
    assert isinstance(body["violations"], list)
    assert len(body["violations"]) == 1
    entry = body["violations"][0]
    assert set(entry) >= {"loc", "type", "msg", "input"}
    assert entry["loc"] == ["body", "value"]


def test_validation_error_in_test_env_returns_field_details(
    test_settings: AppSettings,
) -> None:
    # Non-production environments (dev and test) both expose field-level details.
    assert test_settings.environment == "test"
    with TestClient(_build_with_validate_endpoint(test_settings)) as c:
        resp = c.post("/__validate", json={"value": "not-an-int"})
    assert resp.status_code == 422
    body = resp.json()
    assert "violations" in body
    assert isinstance(body["violations"], list)
    entry = body["violations"][0]
    assert "input" in entry


def test_validation_error_two_field_dev_emits_two_violations(
    test_settings: AppSettings,
) -> None:
    """Spec 3.1: invalid email AND missing required field → 2 violations.

    Each entry exposes ``loc``, ``type``, ``msg``, and ``input``.
    """
    dev_settings = test_settings.model_copy(update={"environment": "development"})
    with TestClient(_build_two_field_validate_endpoint(dev_settings)) as c:
        # Bad email + missing ``name`` field.
        resp = c.post("/__validate_two", json={"email": "not-an-email"})
    assert resp.status_code == 422
    body = resp.json()
    violations = body["violations"]
    assert isinstance(violations, list)
    assert len(violations) == 2
    for entry in violations:
        assert set(entry) >= {"loc", "type", "msg", "input"}
        assert isinstance(entry["loc"], list)
        assert isinstance(entry["type"], str)
        assert isinstance(entry["msg"], str)
    locs = {tuple(v["loc"]) for v in violations}
    assert ("body", "email") in locs
    assert ("body", "name") in locs


def test_validation_error_two_field_production_omits_input(
    test_settings: AppSettings,
) -> None:
    """Spec 3.2: production keeps loc/type/msg but omits the ``input`` key."""
    prod_settings = test_settings.model_copy(update={"environment": "production"})
    with TestClient(_build_two_field_validate_endpoint(prod_settings)) as c:
        resp = c.post("/__validate_two", json={"email": "not-an-email"})
    assert resp.status_code == 422
    body = resp.json()
    violations = body["violations"]
    assert len(violations) == 2
    for entry in violations:
        assert set(entry) == {"loc", "type", "msg"}
        assert "input" not in entry
    locs = {tuple(v["loc"]) for v in violations}
    assert ("body", "email") in locs
    assert ("body", "name") in locs


def test_validation_error_type_is_problem_urn(
    test_settings: AppSettings,
) -> None:
    """Spec 3.3: the body's ``type`` field equals the validation URN."""
    with TestClient(_build_with_validate_endpoint(test_settings)) as c:
        resp = c.post("/__validate", json={"value": "not-an-int"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["type"] == "urn:problem:validation:failed"


def test_validation_error_preserves_nested_loc(
    test_settings: AppSettings,
) -> None:
    """Spec scenario: nested field paths are preserved verbatim in ``loc``."""
    app = build_fastapi_app(test_settings)

    @app.post("/__nested")
    def _nested(body: _NestedOuter) -> dict[str, int]:
        return {"zip": body.address.zip}

    with TestClient(app) as c:
        resp = c.post("/__nested", json={"address": {"zip": "not-an-int"}})
    assert resp.status_code == 422
    body = resp.json()
    locs = [v["loc"] for v in body["violations"]]
    assert ["body", "address", "zip"] in locs
