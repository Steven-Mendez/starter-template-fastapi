"""In-memory :class:`UnitOfWorkPort` for unit and e2e tests."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from src.features._template.application.ports.outbound.unit_of_work import (
    TemplateUoWHandle,
)
from src.features._template.tests.fakes.fake_authorization import FakeAuthorization
from src.features._template.tests.fakes.fake_repository import FakeThingRepository


@dataclass(slots=True)
class FakeUnitOfWork:
    """Yield the in-memory repo + authorization as the active transactional scope.

    The in-memory adapters share the same state across ``begin()`` calls,
    so tests can write in one block and assert in the next without extra
    plumbing. There is no actual rollback — tests that need rollback
    behavior assert against the engine directly.
    """

    things: FakeThingRepository
    authorization: FakeAuthorization

    @contextmanager
    def begin(self) -> Iterator[TemplateUoWHandle]:
        yield TemplateUoWHandle(
            things=self.things,
            authorization=self.authorization,
        )
