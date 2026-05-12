"""SQLModel-backed :class:`UnitOfWorkPort` for the template feature.

The UoW opens one Session per ``begin()`` block and shares it with the
session-scoped thing repository and a session-scoped
``AuthorizationPort`` adapter built by the caller. Commit and rollback
are managed by the context-manager exit.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features._template.adapters.outbound.persistence.sqlmodel.repository import (
    SessionSQLModelThingRepository,
)
from src.features._template.application.ports.outbound.unit_of_work import (
    TemplateUoWHandle,
)
from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)

# Factory: takes a Session, returns a session-scoped AuthorizationPort
# adapter. The caller (composition root) provides this so the template
# feature does not import any concrete authorization adapter.
SessionAuthorizationFactory = Callable[[Session], AuthorizationPort]


@dataclass(slots=True)
class SQLModelUnitOfWork:
    engine: Engine
    session_authorization_factory: SessionAuthorizationFactory

    @contextmanager
    def begin(self) -> Iterator[TemplateUoWHandle]:
        with Session(self.engine, expire_on_commit=False) as session:
            try:
                handle = TemplateUoWHandle(
                    things=SessionSQLModelThingRepository(session=session),
                    authorization=self.session_authorization_factory(session),
                )
                yield handle
                session.commit()
            except Exception:
                session.rollback()
                raise
