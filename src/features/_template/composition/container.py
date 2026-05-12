"""Composition root for the template feature."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlmodel import Session

from src.features._template.adapters.outbound.persistence.sqlmodel.repository import (
    SQLModelThingRepository,
)
from src.features._template.adapters.outbound.persistence.sqlmodel.unit_of_work import (
    SQLModelUnitOfWork,
)
from src.features._template.application.use_cases.create_thing import (
    CreateThingUseCase,
)
from src.features._template.application.use_cases.delete_thing import (
    DeleteThingUseCase,
)
from src.features._template.application.use_cases.get_thing import (
    GetThingUseCase,
)
from src.features._template.application.use_cases.list_things import (
    ListThingsUseCase,
)
from src.features._template.application.use_cases.update_thing import (
    UpdateThingUseCase,
)
from src.features._template.application.use_cases.upload_attachment import (
    UploadAttachmentUseCase,
)
from src.features.authorization.adapters.outbound.sqlmodel.repository import (
    SessionSQLModelAuthorizationAdapter,
)
from src.features.authorization.application.ports.authorization_port import (
    AuthorizationPort,
)
from src.features.authorization.application.ports.outbound.user_authz_version_port import (  # noqa: E501
    UserAuthzVersionPort,
)
from src.features.authorization.application.registry import AuthorizationRegistry
from src.features.file_storage.application.ports.file_storage_port import (
    FileStoragePort,
)

SessionUserAuthzVersionFactory = Callable[[Session], UserAuthzVersionPort]


@dataclass(slots=True)
class TemplateContainer:
    """Bundle of singletons and use-case factories for the template feature."""

    engine: Engine
    repository: SQLModelThingRepository
    uow: SQLModelUnitOfWork
    authorization: AuthorizationPort
    registry: AuthorizationRegistry
    file_storage: FileStoragePort

    # ----- use-case factories -----------------------------------------
    def create_thing(self) -> CreateThingUseCase:
        return CreateThingUseCase(uow=self.uow)

    def get_thing(self) -> GetThingUseCase:
        return GetThingUseCase(repository=self.repository)

    def list_things(self) -> ListThingsUseCase:
        return ListThingsUseCase(
            repository=self.repository, authorization=self.authorization
        )

    def update_thing(self) -> UpdateThingUseCase:
        return UpdateThingUseCase(uow=self.uow)

    def delete_thing(self) -> DeleteThingUseCase:
        return DeleteThingUseCase(uow=self.uow)

    def upload_attachment(self) -> UploadAttachmentUseCase:
        return UploadAttachmentUseCase(
            repository=self.repository, file_storage=self.file_storage
        )

    def shutdown(self) -> None:
        self.engine.dispose()


def build_template_container(
    *,
    postgresql_dsn: str,
    authorization: AuthorizationPort,
    registry: AuthorizationRegistry,
    user_authz_version_factory: SessionUserAuthzVersionFactory,
    file_storage: FileStoragePort,
    pool_size: int = 5,
    max_overflow: int = 10,
    pool_recycle: int = 1800,
    pool_pre_ping: bool = True,
) -> TemplateContainer:
    """Construct the template container, wiring its UoW to authorization."""
    engine = create_engine(
        postgresql_dsn,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
    )
    repository = SQLModelThingRepository(engine=engine)

    def _session_authorization(session: Session) -> AuthorizationPort:
        # Build a session-scoped authorization adapter that participates in
        # the same DB transaction as the thing repository.
        return SessionSQLModelAuthorizationAdapter(
            session=session,
            registry=registry,
            user_authz_version=user_authz_version_factory(session),
        )

    uow = SQLModelUnitOfWork(
        engine=engine,
        session_authorization_factory=_session_authorization,
    )
    return TemplateContainer(
        engine=engine,
        repository=repository,
        uow=uow,
        authorization=authorization,
        registry=registry,
        file_storage=file_storage,
    )
