from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, select

from src.domain.kanban.models import Board, BoardSummary, Card, CardPriority, Column
from src.domain.kanban.repository import KanbanRepositoryPort
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok, Result
from src.infrastructure.persistence.sqlmodel.models import (
    BoardTable,
    CardTable,
    ColumnTable,
)


def sqlite_url_from_path(db_path: str) -> str:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.resolve()}"


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class _BaseSQLModelKanbanRepository(KanbanRepositoryPort):
    def __init__(self) -> None:
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SQLModelKanbanRepository is closed")

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        raise NotImplementedError

    def _commit(self, session: Session) -> None:
        raise NotImplementedError

    def is_ready(self) -> bool:
        if self._closed:
            return False
        try:
            with self._session_scope() as session:
                session.exec(select(1)).one()
            return True
        except SQLAlchemyError:
            return False

    def create_board(self, title: str) -> BoardSummary:
        self._ensure_open()
        board = BoardTable(
            id=str(uuid.uuid4()),
            title=title,
            created_at=datetime.now(timezone.utc),
        )
        with self._session_scope() as session:
            session.add(board)
            self._commit(session)
        return BoardSummary(
            id=board.id,
            title=board.title,
            created_at=_ensure_utc(board.created_at),
        )

    def list_boards(self) -> list[BoardSummary]:
        self._ensure_open()
        with self._session_scope() as session:
            boards = session.exec(select(BoardTable).order_by("created_at")).all()
        return [
            BoardSummary(
                id=board.id,
                title=board.title,
                created_at=_ensure_utc(board.created_at),
            )
            for board in boards
        ]

    def get_board(self, board_id: str) -> Result[Board, KanbanError]:
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
                    Column(
                        id=column.id,
                        board_id=column.board_id,
                        title=column.title,
                        position=column.position,
                        cards=[self._to_card_read(card) for card in cards],
                    )
                )
            return Ok(
                Board(
                    id=board.id,
                    title=board.title,
                    created_at=_ensure_utc(board.created_at),
                    columns=out_columns,
                )
            )

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]:
        self._ensure_open()
        with self._session_scope() as session:
            board = session.get(BoardTable, board_id)
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)
            board.title = title
            session.add(board)
            self._commit(session)
            return Ok(
                BoardSummary(
                    id=board.id,
                    title=board.title,
                    created_at=_ensure_utc(board.created_at),
                )
            )

    def delete_board(self, board_id: str) -> Result[None, KanbanError]:
        self._ensure_open()
        with self._session_scope() as session:
            board = session.get(BoardTable, board_id)
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)
            session.delete(board)
            self._commit(session)
            return Ok(None)

    def find_board_id_by_card(self, card_id: str) -> str | None:
        self._ensure_open()
        with self._session_scope() as session:
            card = session.get(CardTable, card_id)
            if card is None:
                return None
            column = session.get(ColumnTable, card.column_id)
            if column is None:
                return None
            return column.board_id

    def save_board(self, board: Board) -> Result[None, KanbanError]:
        self._ensure_open()
        with self._session_scope() as session:
            db_board = session.get(BoardTable, board.id)
            if db_board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)

            db_board.title = board.title
            session.add(db_board)

            existing_columns = session.exec(
                select(ColumnTable).where(ColumnTable.board_id == board.id)
            ).all()
            existing_column_ids = {column.id for column in existing_columns}
            current_column_ids = {column.id for column in board.columns}
            for column_id in existing_column_ids - current_column_ids:
                column_to_delete = session.get(ColumnTable, column_id)
                if column_to_delete is not None:
                    session.delete(column_to_delete)

            for column in board.columns:
                db_column = session.get(ColumnTable, column.id)
                if db_column is None:
                    db_column = ColumnTable(
                        id=column.id,
                        board_id=board.id,
                        title=column.title,
                        position=column.position,
                    )
                else:
                    db_column.title = column.title
                    db_column.position = column.position
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

            for card_id in existing_board_card_ids - current_board_card_ids:
                card_to_delete = session.get(CardTable, card_id)
                if card_to_delete is not None:
                    session.delete(card_to_delete)

            for column in board.columns:
                for card in column.cards:
                    db_card = session.get(CardTable, card.id)
                    if db_card is None:
                        db_card = CardTable(
                            id=card.id,
                            column_id=column.id,
                            title=card.title,
                            description=card.description,
                            position=card.position,
                            priority=card.priority.value,
                            due_at=card.due_at,
                        )
                    else:
                        db_card.column_id = column.id
                        db_card.title = card.title
                        db_card.description = card.description
                        db_card.position = card.position
                        db_card.priority = card.priority.value
                        db_card.due_at = card.due_at
                    session.add(db_card)

            self._commit(session)
            return Ok(None)

    def find_board_id_by_column(self, column_id: str) -> str | None:
        self._ensure_open()
        with self._session_scope() as session:
            column = session.get(ColumnTable, column_id)
            if column is None:
                return None
            return column.board_id

    @staticmethod
    def _to_card_read(card: CardTable) -> Card:
        return Card(
            id=card.id,
            column_id=card.column_id,
            title=card.title,
            description=card.description,
            position=card.position,
            priority=CardPriority(card.priority),
            due_at=_ensure_utc(card.due_at) if card.due_at else None,
        )


class SQLModelKanbanRepository(_BaseSQLModelKanbanRepository):
    def __init__(self, database_url: str, *, create_schema: bool = True) -> None:
        super().__init__()
        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self._engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        if database_url.startswith("sqlite"):
            from sqlalchemy import event

            @event.listens_for(self._engine, "connect")
            def set_sqlite_pragma(
                dbapi_connection: Any, connection_record: object
            ) -> None:
                del connection_record
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        if create_schema:
            SQLModel.metadata.create_all(self._engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        del exc_type, exc, tb
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._engine.dispose()
        self._closed = True

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        with Session(self._engine, expire_on_commit=False) as session:
            yield session

    def _commit(self, session: Session) -> None:
        session.commit()


class SessionSQLModelKanbanRepository(_BaseSQLModelKanbanRepository):
    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session

    def close(self) -> None:
        self._closed = True

    @contextmanager
    def _session_scope(self) -> Iterator[Session]:
        yield self._session

    def _commit(self, session: Session) -> None:
        del session


class SQLiteKanbanRepository(SQLModelKanbanRepository):
    def __init__(self, db_path: str) -> None:
        super().__init__(sqlite_url_from_path(db_path))
