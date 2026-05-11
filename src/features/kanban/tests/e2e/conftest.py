"""Pytest fixtures that wire a fully composed FastAPI app for Kanban e2e tests.

Under ReBAC, authorization is supplied by an in-memory ``AuthorizationPort``
fake — tests grant relationships explicitly through the fake before
exercising the routes. This keeps the kanban e2e suite focused on
HTTP/use-case wiring; the engine itself is exercised in the auth feature's
own test suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.features.authorization.application.ports.authorization_port import (
    LOOKUP_DEFAULT_LIMIT,
)
from src.features.authorization.application.registry import (
    AuthorizationRegistry,
)
from src.features.authorization.application.types import Relationship
from src.features.kanban.composition import (
    attach_kanban_container,
    mount_kanban_routes,
)
from src.features.kanban.composition.wiring import register_kanban_authorization
from src.features.kanban.tests.fakes import (
    FakeKanbanWiring,
    InMemoryKanbanRepository,
    build_fake_kanban_wiring,
)
from src.platform.api.app_factory import build_fastapi_app
from src.platform.api.dependencies.container import set_app_container
from src.platform.config.settings import AppSettings
from src.platform.shared.principal import Principal
from src.platform.shared.result import Err, Ok


@dataclass(frozen=True, slots=True)
class _Container:
    settings: AppSettings


@dataclass(frozen=True, slots=True)
class _FakeAuthContainer:
    """Stand-in object with the surface ``/health`` reads from app.state."""

    principal_cache: object


_AUTHED_PRINCIPAL = Principal(
    user_id=uuid4(),
    email="test@example.com",
    is_active=True,
    is_verified=True,
    authz_version=1,
)

_READ_ONLY_PRINCIPAL = Principal(
    user_id=uuid4(),
    email="readonly@example.com",
    is_active=True,
    is_verified=True,
    authz_version=1,
)


class _InvalidTokenError(Exception):
    pass


def _fake_resolver(token: str) -> object:
    if token == "test-token":
        return Ok(_AUTHED_PRINCIPAL)
    if token == "read-only-token":
        return Ok(_READ_ONLY_PRINCIPAL)
    return Err(_InvalidTokenError("invalid token"))


@dataclass(slots=True)
class FakeAuthorization:
    """Minimal in-memory ``AuthorizationPort`` fake for kanban e2e tests.

    Mirrors the real engine: every check walks parents through the
    registry until it hits a leaf (a resource type with stored tuples),
    then evaluates the original action against the parent's hierarchy.
    Tests grant a single leaf tuple and exercise inheritance through the
    HTTP layer.
    """

    registry: AuthorizationRegistry
    tuples: set[Relationship] = field(default_factory=set)

    def grant(self, relationship: Relationship) -> None:
        self.tuples.add(relationship)

    def _walk_to_leaf(
        self, resource_type: str, resource_id: str
    ) -> tuple[str, str] | None:
        walked_type, walked_id = resource_type, resource_id
        while not self.registry.has_stored_relations(walked_type):
            parent = self.registry.parent_of(walked_type, walked_id)
            if parent is None:
                return None
            walked_type, walked_id = parent
        return walked_type, walked_id

    def check(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        required = self.registry.relations_for(resource_type, action)
        walked = self._walk_to_leaf(resource_type, resource_id)
        if walked is None:
            return False
        walked_type, walked_id = walked
        expanded = self.registry.expand_relations(walked_type, required)
        return any(
            t
            for t in self.tuples
            if t.resource_type == walked_type
            and t.resource_id == walked_id
            and t.subject_type == "user"
            and t.subject_id == str(user_id)
            and t.relation in expanded
        )

    def lookup_resources(
        self,
        *,
        user_id: UUID,
        action: str,
        resource_type: str,
        limit: int = LOOKUP_DEFAULT_LIMIT,
    ) -> list[str]:
        required = self.registry.relations_for(resource_type, action)
        target_type = self.registry.nearest_leaf_type(resource_type)
        expanded = self.registry.expand_relations(target_type, required)
        ids = sorted(
            {
                t.resource_id
                for t in self.tuples
                if t.resource_type == target_type
                and t.subject_type == "user"
                and t.subject_id == str(user_id)
                and t.relation in expanded
            }
        )
        return ids[:limit]

    def lookup_subjects(
        self,
        *,
        resource_type: str,
        resource_id: str,
        relation: str,
    ) -> list[UUID]:
        expanded = self.registry.expand_relations(resource_type, frozenset({relation}))
        out: list[UUID] = []
        for t in self.tuples:
            if (
                t.resource_type == resource_type
                and t.resource_id == resource_id
                and t.subject_type == "user"
                and t.relation in expanded
            ):
                try:
                    out.append(UUID(t.subject_id))
                except (ValueError, TypeError):
                    continue
        return out

    def write_relationships(self, tuples: list[Relationship]) -> None:
        self.tuples.update(tuples)

    def delete_relationships(self, tuples: list[Relationship]) -> None:
        for t in tuples:
            self.tuples.discard(t)


def _build_app(
    settings: AppSettings,
    wiring: FakeKanbanWiring,
    authorization: FakeAuthorization,
) -> FastAPI:
    app = build_fastapi_app(settings)
    mount_kanban_routes(app)

    @asynccontextmanager
    async def lifespan(lifespan_app: FastAPI):  # type: ignore[no-untyped-def]
        set_app_container(lifespan_app, _Container(settings=settings))
        lifespan_app.state.principal_resolver = _fake_resolver
        lifespan_app.state.authorization = authorization
        lifespan_app.state.auth_container = _FakeAuthContainer(principal_cache=object())
        attach_kanban_container(lifespan_app, wiring.container)
        yield
        lifespan_app.state.container = None
        lifespan_app.state.principal_resolver = None
        lifespan_app.state.authorization = None
        lifespan_app.state.auth_container = None

    app.router.lifespan_context = lifespan
    return app


@pytest.fixture
def repository() -> InMemoryKanbanRepository:
    return InMemoryKanbanRepository()


@pytest.fixture
def registry(repository: InMemoryKanbanRepository) -> AuthorizationRegistry:
    reg = AuthorizationRegistry()
    reg.register_resource_type(
        "system",
        actions={
            "manage_users": frozenset({"admin"}),
            "read_audit": frozenset({"admin"}),
        },
        hierarchy={"admin": frozenset({"admin"})},
    )
    register_kanban_authorization(reg, repository)
    return reg


@pytest.fixture
def authorization(registry: AuthorizationRegistry) -> FakeAuthorization:
    return FakeAuthorization(registry=registry)


@pytest.fixture
def wiring(
    repository: InMemoryKanbanRepository,
    authorization: FakeAuthorization,
) -> FakeKanbanWiring:
    return build_fake_kanban_wiring(
        repository=repository,
        authorization=authorization,
    )


@pytest.fixture
def authed_principal() -> Principal:
    return _AUTHED_PRINCIPAL


@pytest.fixture
def read_only_principal() -> Principal:
    return _READ_ONLY_PRINCIPAL


@pytest.fixture
def client(
    test_settings: AppSettings,
    wiring: FakeKanbanWiring,
    authorization: FakeAuthorization,
) -> Iterator[TestClient]:
    app = _build_app(test_settings, wiring, authorization)
    with TestClient(app) as c:
        c.headers.update({"Authorization": "Bearer test-token"})
        yield c


@pytest.fixture
def unauthenticated_client(
    test_settings: AppSettings,
    wiring: FakeKanbanWiring,
    authorization: FakeAuthorization,
) -> Iterator[TestClient]:
    app = _build_app(test_settings, wiring, authorization)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def read_only_client(
    test_settings: AppSettings,
    wiring: FakeKanbanWiring,
    authorization: FakeAuthorization,
) -> Iterator[TestClient]:
    """Client authenticated as a different user with no granted relationships."""
    app = _build_app(test_settings, wiring, authorization)
    with TestClient(app) as c:
        c.headers.update({"Authorization": "Bearer read-only-token"})
        yield c


@pytest.fixture
def client_without_jwt_secret(
    test_settings: AppSettings,
    wiring: FakeKanbanWiring,
    authorization: FakeAuthorization,
) -> Iterator[TestClient]:
    settings = test_settings.model_copy(update={"auth_jwt_secret_key": None})
    app = _build_app(settings, wiring, authorization)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client_with_unreachable_redis(
    test_settings: AppSettings,
    wiring: FakeKanbanWiring,
    authorization: FakeAuthorization,
) -> Iterator[TestClient]:
    settings = test_settings.model_copy(
        update={"auth_redis_url": "redis://127.0.0.1:1/0"}
    )
    app = _build_app(settings, wiring, authorization)
    with TestClient(app) as c:
        yield c
