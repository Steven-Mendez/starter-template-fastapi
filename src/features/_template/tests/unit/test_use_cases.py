"""Unit tests for the template feature's use cases (with in-memory adapters)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from src.features._template.application.errors import ApplicationError
from src.features._template.application.use_cases.create_thing import (
    CreateThingCommand,
    CreateThingUseCase,
)
from src.features._template.application.use_cases.delete_thing import (
    DeleteThingCommand,
    DeleteThingUseCase,
)
from src.features._template.application.use_cases.get_thing import (
    GetThingQuery,
    GetThingUseCase,
)
from src.features._template.application.use_cases.list_things import (
    ListThingsQuery,
    ListThingsUseCase,
)
from src.features._template.application.use_cases.update_thing import (
    UpdateThingCommand,
    UpdateThingUseCase,
)
from src.features._template.tests.fakes.fake_authorization import FakeAuthorization
from src.features._template.tests.fakes.fake_repository import FakeThingRepository
from src.features._template.tests.fakes.fake_uow import FakeUnitOfWork
from src.features.authorization.tests.contracts.registry_helper import (
    make_test_registry,
)
from src.platform.shared.result import Err, Ok

pytestmark = pytest.mark.unit


def _bundle() -> tuple[FakeUnitOfWork, FakeAuthorization, FakeThingRepository]:
    repo = FakeThingRepository()
    authz = FakeAuthorization(registry=make_test_registry())
    return FakeUnitOfWork(things=repo, authorization=authz), authz, repo


def test_create_thing_writes_owner_tuple() -> None:
    uow, authz, repo = _bundle()
    owner = uuid4()
    result = CreateThingUseCase(uow=uow).execute(
        CreateThingCommand(name="One", owner_id=owner)
    )
    assert isinstance(result, Ok)
    thing = result.value
    assert repo.get(thing.id) is not None
    assert authz.check(
        user_id=owner, action="delete", resource_type="thing", resource_id=str(thing.id)
    )


def test_create_thing_rejects_empty_name() -> None:
    uow, _, repo = _bundle()
    result = CreateThingUseCase(uow=uow).execute(
        CreateThingCommand(name="", owner_id=uuid4())
    )
    assert isinstance(result, Err)
    assert result.error is ApplicationError.NAME_REQUIRED
    # No partial state.
    assert repo.list_by_ids([]) == []


def test_get_thing_returns_not_found_when_missing() -> None:
    _, _, repo = _bundle()
    result = GetThingUseCase(repository=repo).execute(GetThingQuery(thing_id=uuid4()))
    assert isinstance(result, Err)
    assert result.error is ApplicationError.NOT_FOUND


def test_list_things_filters_by_authorization() -> None:
    uow, authz, repo = _bundle()
    u1, u2 = uuid4(), uuid4()
    created = CreateThingUseCase(uow=uow).execute(
        CreateThingCommand(name="for u1", owner_id=u1)
    )
    assert isinstance(created, Ok)
    t1 = created.value
    CreateThingUseCase(uow=uow).execute(CreateThingCommand(name="for u2", owner_id=u2))
    listed = ListThingsUseCase(repository=repo, authorization=authz).execute(
        ListThingsQuery(user_id=u1)
    )
    assert [t.id for t in listed] == [t1.id]


def test_update_thing_renames_and_returns_new_instance() -> None:
    uow, _, _ = _bundle()
    created = CreateThingUseCase(uow=uow).execute(
        CreateThingCommand(name="Old", owner_id=uuid4())
    )
    assert isinstance(created, Ok)
    thing = created.value
    result = UpdateThingUseCase(uow=uow).execute(
        UpdateThingCommand(thing_id=thing.id, new_name="New")
    )
    assert isinstance(result, Ok)
    assert result.value.name == "New"


def test_delete_thing_removes_resource_and_tuples() -> None:
    uow, authz, repo = _bundle()
    owner = uuid4()
    created = CreateThingUseCase(uow=uow).execute(
        CreateThingCommand(name="X", owner_id=owner)
    )
    assert isinstance(created, Ok)
    thing = created.value
    result = DeleteThingUseCase(uow=uow).execute(DeleteThingCommand(thing_id=thing.id))
    assert isinstance(result, Ok)
    assert repo.get(thing.id) is None
    assert not authz.check(
        user_id=owner, action="read", resource_type="thing", resource_id=str(thing.id)
    )
