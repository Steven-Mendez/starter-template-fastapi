from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.platform.api.app_factory import build_fastapi_app
from src.platform.api.dependencies.container import set_app_container
from src.platform.config.settings import AppSettings

pytestmark = pytest.mark.unit


@dataclass(frozen=True, slots=True)
class _Container:
    settings: AppSettings


def test_lifespan_sets_and_clears_container(test_settings: AppSettings) -> None:
    app = build_fastapi_app(test_settings)
    constructed: list[_Container] = []
    cleared = {"value": False}

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        container = _Container(settings=test_settings)
        constructed.append(container)
        set_app_container(lifespan_app, container)
        try:
            yield
        finally:
            lifespan_app.state.container = None
            cleared["value"] = True

    app.router.lifespan_context = lifespan
    with TestClient(app) as c:
        # The container is set during startup, before the first request
        resp = c.get("/")
        assert resp.status_code == 200
    assert len(constructed) == 1
    assert cleared["value"] is True
