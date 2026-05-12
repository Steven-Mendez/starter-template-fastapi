"""SQLModel-backed :class:`ThingRepositoryPort` implementation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from src.features._template.adapters.outbound.persistence.sqlmodel.models import (
    ThingTable,
)
from src.features._template.domain.models.thing import Thing


def _to_domain(row: ThingTable) -> Thing:
    return Thing(
        id=row.id,
        name=row.name,
        owner_id=row.owner_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_row(thing: Thing) -> ThingTable:
    return ThingTable(
        id=thing.id,
        name=thing.name,
        owner_id=thing.owner_id,
        created_at=thing.created_at,
        updated_at=thing.updated_at,
    )


@dataclass(slots=True)
class SQLModelThingRepository:
    """Adapter that opens its own short-lived session per call."""

    engine: Engine

    def add(self, thing: Thing) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            session.add(_to_row(thing))
            session.commit()

    def get(self, thing_id: UUID) -> Thing | None:
        with Session(self.engine) as session:
            row = session.get(ThingTable, thing_id)
            return _to_domain(row) if row else None

    def list_by_ids(self, ids: list[UUID]) -> list[Thing]:
        if not ids:
            return []
        with Session(self.engine) as session:
            stmt = select(ThingTable).where(ThingTable.id.in_(ids))  # type: ignore[attr-defined]
            return [_to_domain(r) for r in session.exec(stmt).all()]

    def update(self, thing: Thing) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(ThingTable, thing.id)
            if row is None:
                raise KeyError(f"Thing {thing.id} does not exist")
            row.name = thing.name
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
            session.commit()

    def delete(self, thing_id: UUID) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(ThingTable, thing_id)
            if row is None:
                return
            session.delete(row)
            session.commit()


@dataclass(slots=True)
class SessionSQLModelThingRepository:
    """Adapter that borrows a Session managed by an outer unit-of-work.

    All writes are staged on the shared session; commit and rollback are
    owned by the UoW.
    """

    session: Session

    def add(self, thing: Thing) -> None:
        self.session.add(_to_row(thing))

    def get(self, thing_id: UUID) -> Thing | None:
        row = self.session.get(ThingTable, thing_id)
        return _to_domain(row) if row else None

    def list_by_ids(self, ids: list[UUID]) -> list[Thing]:
        if not ids:
            return []
        stmt = select(ThingTable).where(ThingTable.id.in_(ids))  # type: ignore[attr-defined]
        return [_to_domain(r) for r in self.session.exec(stmt).all()]

    def update(self, thing: Thing) -> None:
        row = self.session.get(ThingTable, thing.id)
        if row is None:
            raise KeyError(f"Thing {thing.id} does not exist")
        row.name = thing.name
        row.updated_at = datetime.now(timezone.utc)
        self.session.add(row)

    def delete(self, thing_id: UUID) -> None:
        row = self.session.get(ThingTable, thing_id)
        if row is not None:
            self.session.delete(row)
