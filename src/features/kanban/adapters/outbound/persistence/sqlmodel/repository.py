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
from types import TracebackType
from typing import Self

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


class PersistenceConflictError(RuntimeError):
    """Raised when a stale aggregate write is detected."""


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
        """Probe the database with ``SELECT 1`` to power the readiness endpoint."""
        if self._closed:
            return False
        try:
            with self._session_scope() as session:
                session.exec(select(1)).one()
            return True
        except SQLAlchemyError:
            return False

    def list_all(self) -> list[BoardSummary]:
        """List boards as :class:`BoardSummary`, ordered by creation time."""
        self._ensure_open()
        with self._session_scope() as session:
            boards = session.exec(select(BoardTable).order_by("created_at")).all()
        return [board_table_to_read_model(board) for board in boards]

    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]:
        """Hydrate a complete :class:`Board` aggregate (columns + cards) by id."""
        self._ensure_open()
        with self._session_scope() as session:
            board = session.get(BoardTable, board_id)
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)

            columns = session.exec(
                select(ColumnTable)
                .where(ColumnTable.board_id == board_id)
                .order_by("position")
            ).all()
            out_columns: list[Column] = []
            for column in columns:
                cards = session.exec(
                    select(CardTable)
                    .where(CardTable.column_id == column.id)
                    .order_by("position")
                ).all()
                out_columns.append(
                    column_table_to_domain(
                        row=column,
                        cards=[card_table_to_domain(card) for card in cards],
                    )
                )
            return Ok(board_table_to_domain(row=board, columns=out_columns))

    def find_card_by_id(self, card_id: str) -> Result[Card, KanbanError]:
        """Load a single card by id without traversing its parent board."""
        self._ensure_open()
        with self._session_scope() as session:
            card = session.get(CardTable, card_id)
            if card is None:
                return Err(KanbanError.CARD_NOT_FOUND)
            return Ok(card_table_to_domain(card))

    def remove(self, board_id: str) -> Result[None, KanbanError]:
        """Delete the board row, cascading to its columns and cards via foreign keys."""
        self._ensure_open()
        with self._write_session_scope() as session:
            board = session.get(BoardTable, board_id)
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)
            session.delete(board)
            return Ok(None)

    def find_board_id_by_card(self, card_id: str) -> str | None:
        """Return the parent board id for a card, walking through its column."""
        self._ensure_open()
        with self._session_scope() as session:
            card = session.get(CardTable, card_id)
            if card is None:
                return None
            column = session.get(ColumnTable, card.column_id)
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
            db_board = session.get(BoardTable, board.id)
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
                db_board.version += 1
            session.add(db_board)
            board.version = db_board.version

            existing_columns = session.exec(
                select(ColumnTable).where(ColumnTable.board_id == board.id)
            ).all()
            # The domain aggregate is authoritative. Rows missing from the
            # current snapshot are intentionally removed from persistence.
            existing_column_ids = {column.id for column in existing_columns}
            current_column_ids = {column.id for column in board.columns}
            for column_id in existing_column_ids - current_column_ids:
                column_to_delete = session.get(ColumnTable, column_id)
                if column_to_delete is not None:
                    session.delete(column_to_delete)

            for column in board.columns:
                db_column = session.get(ColumnTable, column.id)
                mapped_column = column_domain_to_table(column, board_id=board.id)
                if db_column is None:
                    db_column = mapped_column
                else:
                    db_column.board_id = mapped_column.board_id
                    db_column.title = mapped_column.title
                    db_column.position = mapped_column.position
                session.add(db_column)

            existing_board_cards = session.exec(
                select(CardTable)
                .join(ColumnTable)
                .where(ColumnTable.board_id == board.id)
            ).all()
            existing_board_card_ids = {card.id for card in existing_board_cards}
            current_board_card_ids = {
                card.id for column in board.columns for card in column.cards
            }

            # Card deletion follows the same aggregate-snapshot rule as columns.
            for card_id in existing_board_card_ids - current_board_card_ids:
                card_to_delete = session.get(CardTable, card_id)
                if card_to_delete is not None:
                    session.delete(card_to_delete)

            for column in board.columns:
                for card in column.cards:
                    db_card = session.get(CardTable, card.id)
                    mapped_card = card_domain_to_table(card, column_id=column.id)
                    if db_card is None:
                        db_card = mapped_card
                    else:
                        db_card.column_id = mapped_card.column_id
                        db_card.title = mapped_card.title
                        db_card.description = mapped_card.description
                        db_card.position = mapped_card.position
                        db_card.priority = mapped_card.priority
                        db_card.due_at = mapped_card.due_at
                    session.add(db_card)

    def find_board_id_by_column(self, column_id: str) -> str | None:
        """Return the parent board id for a column directly from the row."""
        self._ensure_open()
        with self._session_scope() as session:
            column = session.get(ColumnTable, column_id)
            if column is None:
                return None
            return column.board_id


class SQLModelKanbanRepository(_BaseSQLModelKanbanRepository):
    """Production-flavour repository that owns its own engine and connection pool."""

    def __init__(self, database_url: str, *, create_schema: bool = True) -> None:
        """Build a repository connected to a PostgreSQL DSN.

        Args:
            database_url: SQLAlchemy-compatible PostgreSQL DSN.
            create_schema: Create tables before use; convenient for local
                development but disabled in production where Alembic owns
                the schema.

        Raises:
            ValueError: If ``database_url`` is not a PostgreSQL DSN.
        """
        super().__init__()
        if not database_url.startswith("postgresql"):
            msg = "SQLModelKanbanRepository supports PostgreSQL DSNs only"
            raise ValueError(msg)
        self._engine = create_engine(database_url, pool_pre_ping=True)

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
