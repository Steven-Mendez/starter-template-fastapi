"""SQLModel-backed implementation of the Kanban outbound repository ports.

Provides two flavours of the same logic:

* :class:`SQLModelKanbanRepository` owns its own engine, sessions, and
  shutdown lifecycle; suitable for production use.
* :class:`SessionSQLModelKanbanRepository` borrows an existing session
  driven by the unit-of-work, so writes participate in the transaction
  the use case has opened explicitly.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, select

from src.features.kanban.adapters.outbound.persistence.sqlmodel.mappers import (
    board_domain_to_table,
    board_table_to_domain,
    board_table_to_read_model,
    card_domain_to_table,
    card_table_to_domain,
    column_domain_to_table,
    column_table_to_domain,
)
from src.features.kanban.adapters.outbound.persistence.sqlmodel.models import (
    BoardTable,
    CardTable,
    ColumnTable,
)
from src.features.kanban.application.persistence_errors import PersistenceConflictError
from src.features.kanban.application.ports.outbound.kanban_command_repository import (
    KanbanCommandRepositoryPort,
)
from src.features.kanban.application.ports.outbound.kanban_lookup_repository import (
    KanbanLookupRepositoryPort,
)
from src.features.kanban.application.ports.outbound.kanban_query_repository import (
    KanbanQueryRepositoryPort,
)
from src.features.kanban.domain.errors import KanbanError
from src.features.kanban.domain.models import Board, BoardSummary, Card, Column
from src.platform.shared.result import Err, Ok, Result

# Re-export so existing imports of PersistenceConflictError from this module
# keep working.
__all__ = [
    "PersistenceConflictError",
    "SQLModelKanbanRepository",
    "SessionSQLModelKanbanRepository",
]


class _BaseSQLModelKanbanRepository(
    KanbanQueryRepositoryPort,
    KanbanCommandRepositoryPort,
    KanbanLookupRepositoryPort,
):
    """Shared implementation of the three repository ports backed by SQLModel.

    Subclasses provide the session strategy (own-engine vs unit-of-work
    session) by overriding :meth:`_session_scope` and
    :meth:`_write_session_scope`.
    """

    def __init__(self) -> None:
        self._closed = False

    def _ensure_open(self) -> None:
        """Raise ``RuntimeError`` if :meth:`close` has already been invoked."""
        if self._closed:
            raise RuntimeError("SQLModelKanbanRepository is closed")

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        raise NotImplementedError

    @contextmanager
    def _write_session_scope(self) -> Iterator[Session]:
        raise NotImplementedError

    def is_ready(self) -> bool:
        """Probe DB connectivity and confirm Alembic has initialized the schema."""
        if self._closed:
            return False
        try:
            with self._session_scope() as session:
                session.exec(select(1)).one()
                session.execute(text("SELECT 1 FROM alembic_version LIMIT 1")).one()
            return True
        except SQLAlchemyError:
            return False

    def list_all(self) -> list[BoardSummary]:
        """List active boards as :class:`BoardSummary`, ordered by creation time."""
        self._ensure_open()
        with self._session_scope() as session:
            boards = session.exec(
                select(BoardTable)
                .where(BoardTable.deleted_at.is_(None))  # type: ignore[union-attr]
                .order_by("created_at")
            ).all()
        return [board_table_to_read_model(board) for board in boards]

    def list_by_ids(self, board_ids: list[str]) -> list[BoardSummary]:
        """List active boards whose ids are in ``board_ids``, ordered by creation."""
        if not board_ids:
            return []
        self._ensure_open()
        with self._session_scope() as session:
            boards = session.exec(
                select(BoardTable)
                .where(BoardTable.id.in_(board_ids))  # type: ignore[attr-defined]
                .where(BoardTable.deleted_at.is_(None))  # type: ignore[union-attr]
                .order_by("created_at")
            ).all()
        return [board_table_to_read_model(board) for board in boards]

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        """Hydrate a complete :class:`Board` aggregate (columns + cards) by id."""
        self._ensure_open()
        with self._session_scope() as session:
            board = session.exec(
                select(BoardTable)
                .where(BoardTable.id == board_id)
                .where(BoardTable.deleted_at.is_(None))  # type: ignore[union-attr]
            ).one_or_none()
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)

            columns = session.exec(
                select(ColumnTable)
                .where(ColumnTable.board_id == board_id)
                .where(ColumnTable.deleted_at.is_(None))  # type: ignore[union-attr]
                .order_by("position")
            ).all()
            column_ids = [column.id for column in columns]

            # Fetch every card on the board in one IN() query and bucket
            # them by column_id, instead of issuing one query per column.
            cards_by_column: dict[str, list[CardTable]] = {
                column_id: [] for column_id in column_ids
            }
            if column_ids:
                cards = session.exec(
                    select(CardTable)
                    .where(CardTable.column_id.in_(column_ids))  # type: ignore[attr-defined]
                    .where(CardTable.deleted_at.is_(None))  # type: ignore[union-attr]
                    .order_by("position")
                ).all()
                for card in cards:
                    cards_by_column.setdefault(card.column_id, []).append(card)

            out_columns: list[Column] = [
                column_table_to_domain(
                    row=column,
                    cards=[
                        card_table_to_domain(card)
                        for card in cards_by_column.get(column.id, [])
                    ],
                )
                for column in columns
            ]
            return Ok(board_table_to_domain(row=board, columns=out_columns))

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]:
        """Load a single active card by id without traversing its parent board."""
        self._ensure_open()
        with self._session_scope() as session:
            card = session.exec(
                select(CardTable)
                .where(CardTable.id == card_id)
                .where(CardTable.deleted_at.is_(None))  # type: ignore[union-attr]
            ).one_or_none()
            if card is None:
                return Err(KanbanError.CARD_NOT_FOUND)
            return Ok(card_table_to_domain(card))

    def remove(
        self, board_id: str, *, actor_id: UUID | None = None
    ) -> Result[None, KanbanError]:
        """Soft-delete the board, cascading to its active columns and cards.

        All affected rows share a fresh ``deletion_id`` so :meth:`restore`
        can revert the exact set of rows that were removed in this call.
        """
        self._ensure_open()
        with self._write_session_scope() as session:
            board = session.exec(
                select(BoardTable)
                .where(BoardTable.id == board_id)
                .where(BoardTable.deleted_at.is_(None))  # type: ignore[union-attr]
            ).one_or_none()
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)
            now = datetime.now(timezone.utc)
            deletion_id = uuid4()
            session.execute(
                update(CardTable)
                .where(
                    CardTable.column_id.in_(  # type: ignore[attr-defined]
                        select(ColumnTable.id).where(ColumnTable.board_id == board_id)
                    )
                )
                .where(CardTable.deleted_at.is_(None))  # type: ignore[union-attr]
                .values(deleted_at=now, deletion_id=deletion_id, updated_by=actor_id)
            )
            session.execute(
                update(ColumnTable)
                .where(cast(Any, ColumnTable.board_id == board_id))
                .where(cast(Any, ColumnTable.deleted_at).is_(None))
                .values(deleted_at=now, deletion_id=deletion_id, updated_by=actor_id)
            )
            session.execute(
                update(BoardTable)
                .where(cast(Any, BoardTable.id == board_id))
                .where(cast(Any, BoardTable.deleted_at).is_(None))
                .values(deleted_at=now, deletion_id=deletion_id, updated_by=actor_id)
            )
            return Ok(None)

    def restore(
        self, board_id: str, *, actor_id: UUID | None = None
    ) -> Result[None, KanbanError]:
        """Reverse a previous :meth:`remove`, restoring the matching cascade.

        Looks up the board's ``deletion_id`` and clears soft-delete on every
        row that was deleted in the same operation, so a deleted-restored-
        redeleted board does not accidentally surface stale children from
        an earlier deletion.
        """
        self._ensure_open()
        with self._write_session_scope() as session:
            board = session.exec(
                select(BoardTable)
                .where(BoardTable.id == board_id)
                .where(BoardTable.deleted_at.is_not(None))  # type: ignore[union-attr]
            ).one_or_none()
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)
            deletion_id = board.deletion_id
            if deletion_id is None:
                # Defensive: ``deleted_at IS NOT NULL AND deletion_id IS NULL``
                # should never happen because ``remove`` always stamps both.
                return Err(KanbanError.BOARD_NOT_FOUND)
            for table in (CardTable, ColumnTable, BoardTable):
                session.execute(
                    update(table)
                    .where(cast(Any, table.deletion_id == deletion_id))
                    .values(deleted_at=None, deletion_id=None, updated_by=actor_id)
                )
            return Ok(None)

    def find_board_id_by_card(self, card_id: str) -> str | None:
        """Return the parent board id for an active card."""
        self._ensure_open()
        with self._session_scope() as session:
            card = session.exec(
                select(CardTable)
                .where(CardTable.id == card_id)
                .where(CardTable.deleted_at.is_(None))  # type: ignore[union-attr]
            ).one_or_none()
            if card is None:
                return None
            column = session.exec(
                select(ColumnTable)
                .where(ColumnTable.id == card.column_id)
                .where(ColumnTable.deleted_at.is_(None))  # type: ignore[union-attr]
            ).one_or_none()
            if column is None:
                return None
            return column.board_id

    def save(self, board: Board) -> None:
        """Persist the entire board aggregate as a single snapshot.

        Treating the board as a snapshot keeps cross-row consistency in
        one place: rows that are no longer present in the in-memory
        aggregate are deleted, and a stale ``version`` raises
        :class:`PersistenceConflictError` instead of clobbering newer data.

        Raises:
            PersistenceConflictError: If the in-memory ``version`` does
                not match the persisted one (optimistic-lock failure).
        """
        self._ensure_open()
        with self._write_session_scope() as session:
            # Take a row-level lock on the parent board so concurrent
            # writers (move + delete on different children) serialize
            # through this aggregate root. Combined with the optimistic
            # ``version`` check, this prevents lost updates that would
            # otherwise slip through under READ COMMITTED isolation.
            db_board = session.exec(
                select(BoardTable).where(BoardTable.id == board.id).with_for_update()
            ).one_or_none()
            mapped_board = board_domain_to_table(board)
            if db_board is None:
                db_board = mapped_board
                db_board.version = 1
            else:
                if db_board.version != board.version:
                    msg = f"Stale board write detected for {board.id}"
                    raise PersistenceConflictError(msg)
                db_board.title = mapped_board.title
                db_board.created_at = mapped_board.created_at
                db_board.updated_by = mapped_board.updated_by
                db_board.version += 1
            session.add(db_board)
            board.version = db_board.version

            # Bulk-fetch existing children once and index by id so the diff
            # below runs in O(n) without per-row session.get() round-trips.
            # Only active rows participate in the snapshot diff — soft-deleted
            # children belong to a tombstoned cascade and must not influence
            # the current write.
            existing_columns = {
                column.id: column
                for column in session.exec(
                    select(ColumnTable)
                    .where(ColumnTable.board_id == board.id)
                    .where(ColumnTable.deleted_at.is_(None))  # type: ignore[union-attr]
                ).all()
            }
            existing_cards = {
                card.id: card
                for card in session.exec(
                    select(CardTable)
                    .join(ColumnTable)
                    .where(ColumnTable.board_id == board.id)
                    .where(CardTable.deleted_at.is_(None))  # type: ignore[union-attr]
                ).all()
            }

            current_column_ids = {column.id for column in board.columns}
            current_card_ids = {
                card.id for column in board.columns for card in column.cards
            }

            # Delete rows missing from the current snapshot in one statement
            # per table — far cheaper than per-row session.delete() loops.
            removed_card_ids = set(existing_cards) - current_card_ids
            if removed_card_ids:
                session.execute(
                    delete(CardTable).where(
                        CardTable.id.in_(removed_card_ids)  # type: ignore[attr-defined]
                    )
                )
            removed_column_ids = set(existing_columns) - current_column_ids
            if removed_column_ids:
                session.execute(
                    delete(ColumnTable).where(
                        ColumnTable.id.in_(removed_column_ids)  # type: ignore[attr-defined]
                    )
                )

            for column in board.columns:
                mapped_column = column_domain_to_table(column, board_id=board.id)
                db_column = existing_columns.get(column.id)
                if db_column is None:
                    session.add(mapped_column)
                else:
                    db_column.board_id = mapped_column.board_id
                    db_column.title = mapped_column.title
                    db_column.position = mapped_column.position
                    db_column.updated_by = mapped_column.updated_by
                    session.add(db_column)

            # Flush column inserts before cards reference their ids: the
            # foreign key (cards.column_id → columns_.id) is enforced by
            # the database, and the tables don't declare an ORM
            # relationship that would let SQLAlchemy infer ordering.
            session.flush()

            for column in board.columns:
                for card in column.cards:
                    mapped_card = card_domain_to_table(card, column_id=column.id)
                    db_card = existing_cards.get(card.id)
                    if db_card is None:
                        session.add(mapped_card)
                    else:
                        db_card.column_id = mapped_card.column_id
                        db_card.title = mapped_card.title
                        db_card.description = mapped_card.description
                        db_card.position = mapped_card.position
                        db_card.priority = mapped_card.priority
                        db_card.due_at = mapped_card.due_at
                        db_card.updated_by = mapped_card.updated_by
                        session.add(db_card)

    def find_board_id_by_column(self, column_id: str) -> str | None:
        """Return the parent board id for an active column."""
        self._ensure_open()
        with self._session_scope() as session:
            column = session.exec(
                select(ColumnTable)
                .where(ColumnTable.id == column_id)
                .where(ColumnTable.deleted_at.is_(None))  # type: ignore[union-attr]
            ).one_or_none()
            if column is None:
                return None
            return column.board_id


class SQLModelKanbanRepository(_BaseSQLModelKanbanRepository):
    """Production-flavour repository that owns its own engine and connection pool."""

    def __init__(
        self,
        database_url: str,
        *,
        create_schema: bool = True,
        pool_size: int = 5,
        max_overflow: int = 10,
        pool_recycle: int = 1800,
        pool_pre_ping: bool = True,
    ) -> None:
        """Build a repository connected to a PostgreSQL DSN.

        Args:
            database_url: SQLAlchemy-compatible PostgreSQL DSN.
            create_schema: Create tables before use; convenient for local
                development but disabled in production where Alembic owns
                the schema.
            pool_size, max_overflow, pool_recycle, pool_pre_ping: Standard
                SQLAlchemy connection-pool tuning. Defaults are suitable for
                small services; production deployments should size these
                against expected concurrency and any pooler in front of the DB.

        Raises:
            ValueError: If ``database_url`` is not a PostgreSQL DSN.
        """
        super().__init__()
        if not database_url.startswith("postgresql"):
            msg = "SQLModelKanbanRepository supports PostgreSQL DSNs only"
            raise ValueError(msg)
        self._engine = create_engine(
            database_url,
            pool_pre_ping=pool_pre_ping,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
        )

        if create_schema:
            SQLModel.metadata.create_all(self._engine)

    @classmethod
    def from_engine(
        cls, engine: Engine, *, create_schema: bool = False
    ) -> "SQLModelKanbanRepository":
        """Build a repository on top of an existing engine, bypassing the DSN guard.

        Used by tests to inject a SQLite in-memory engine that the
        ``__init__`` validator would otherwise reject.
        """
        instance = cls.__new__(cls)
        _BaseSQLModelKanbanRepository.__init__(instance)
        instance._engine = engine
        if create_schema:
            SQLModel.metadata.create_all(engine)
        return instance

    @property
    def engine(self) -> Engine:
        """Expose the underlying engine for tooling that needs raw access."""
        return self._engine

    def __enter__(self) -> Self:
        """Allow use as a context manager; the engine is disposed on exit."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Dispose the connection pool when leaving the ``with`` block."""
        del exc_type, exc, tb
        self.close()

    def close(self) -> None:
        """Dispose the engine; idempotent so it can be called more than once safely."""
        if self._closed:
            return
        self._engine.dispose()
        self._closed = True

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        with Session(self._engine, expire_on_commit=False) as session:
            yield session

    @contextmanager
    def _write_session_scope(self) -> Iterator[Session]:
        with Session(self._engine, expire_on_commit=False) as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise


class SessionSQLModelKanbanRepository(_BaseSQLModelKanbanRepository):
    """Repository flavour that borrows an existing session managed by the unit-of-work.

    Use cases that need atomic multi-step writes hold the unit-of-work
    open and pass its session to this repository; closing here only
    flips the internal flag because the session lifecycle belongs to the
    unit-of-work.
    """

    def __init__(self, session: Session) -> None:
        """Wrap the given session and reuse it for both reads and writes."""
        super().__init__()
        self._session = session

    def close(self) -> None:
        """Mark the repository closed without touching the borrowed session."""
        self._closed = True

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        yield self._session

    @contextmanager
    def _write_session_scope(self) -> Iterator[Session]:
        yield self._session
