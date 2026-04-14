from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import TracebackType
from typing import Self, cast

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, SQLModel, create_engine, select

from kanban.card_move_specifications import (
    CardMoveCandidate,
    SameBoardMoveSpecification,
    TargetColumnExistsSpecification,
)
from kanban.errors import KanbanError
from kanban.repository import KanbanRepository
from kanban.result import Err, Ok, Result
from kanban.schemas import BoardDetail, BoardSummary, CardPriority, CardRead, ColumnRead
from kanban.sqlmodel_models import BoardTable, CardTable, ColumnTable


def sqlite_url_from_path(db_path: str) -> str:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path.resolve()}"


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SQLModelKanbanRepository(KanbanRepository):
    def __init__(self, database_url: str, *, create_schema: bool = True) -> None:
        connect_args: dict[str, object] = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self._engine = create_engine(
            database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )
        self._closed = False
        if create_schema:
            SQLModel.metadata.create_all(self._engine)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._engine.dispose()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("SQLModelKanbanRepository is closed")

    def is_ready(self) -> bool:
        if self._closed:
            return False
        try:
            with Session(self._engine, expire_on_commit=False) as session:
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
        with Session(self._engine, expire_on_commit=False) as session:
            session.add(board)
            session.commit()
        return BoardSummary(
            id=board.id,
            title=board.title,
            created_at=_ensure_utc(board.created_at),
        )

    def list_boards(self) -> list[BoardSummary]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            boards = session.exec(select(BoardTable).order_by("created_at")).all()
        return [
            BoardSummary(
                id=board.id,
                title=board.title,
                created_at=_ensure_utc(board.created_at),
            )
            for board in boards
        ]

    def get_board(self, board_id: str) -> Result[BoardDetail, KanbanError]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            board = session.get(BoardTable, board_id)
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)

            columns = session.exec(
                select(ColumnTable)
                .where(ColumnTable.board_id == board_id)
                .order_by("position")
            ).all()
            out_columns: list[ColumnRead] = []
            for column in columns:
                cards = session.exec(
                    select(CardTable)
                    .where(CardTable.column_id == column.id)
                    .order_by("position")
                ).all()
                out_columns.append(
                    ColumnRead(
                        id=column.id,
                        board_id=column.board_id,
                        title=column.title,
                        position=column.position,
                        cards=[self._to_card_read(card) for card in cards],
                    )
                )
            return Ok(
                BoardDetail(
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
        with Session(self._engine, expire_on_commit=False) as session:
            board = session.get(BoardTable, board_id)
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)
            board.title = title
            session.add(board)
            session.commit()
            return Ok(
                BoardSummary(
                    id=board.id,
                    title=board.title,
                    created_at=_ensure_utc(board.created_at),
                )
            )

    def delete_board(self, board_id: str) -> Result[None, KanbanError]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            board = session.get(BoardTable, board_id)
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)
            session.delete(board)
            session.commit()
            return Ok(None)

    def create_column(
        self, board_id: str, title: str
    ) -> Result[ColumnRead, KanbanError]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            board = session.get(BoardTable, board_id)
            if board is None:
                return Err(KanbanError.BOARD_NOT_FOUND)

            max_position = session.exec(
                select(func.max(ColumnTable.position)).where(
                    ColumnTable.board_id == board_id
                )
            ).one()
            position = (cast(int | None, max_position) or -1) + 1

            column = ColumnTable(
                id=str(uuid.uuid4()),
                board_id=board_id,
                title=title,
                position=position,
            )
            session.add(column)
            session.commit()
            return Ok(
                ColumnRead(
                    id=column.id,
                    board_id=column.board_id,
                    title=column.title,
                    position=column.position,
                    cards=[],
                )
            )

    def delete_column(self, column_id: str) -> Result[None, KanbanError]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            column = session.get(ColumnTable, column_id)
            if column is None:
                return Err(KanbanError.COLUMN_NOT_FOUND)
            session.delete(column)
            session.commit()
            return Ok(None)

    def create_card(
        self,
        column_id: str,
        title: str,
        description: str | None,
        *,
        priority: CardPriority = CardPriority.MEDIUM,
        due_at: datetime | None = None,
    ) -> Result[CardRead, KanbanError]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            column = session.get(ColumnTable, column_id)
            if column is None:
                return Err(KanbanError.COLUMN_NOT_FOUND)

            max_position = session.exec(
                select(func.max(CardTable.position)).where(
                    CardTable.column_id == column_id
                )
            ).one()
            position = (cast(int | None, max_position) or -1) + 1

            card = CardTable(
                id=str(uuid.uuid4()),
                column_id=column_id,
                title=title,
                description=description,
                position=position,
                priority=priority.value,
                due_at=due_at,
            )
            session.add(card)
            session.commit()
            return Ok(self._to_card_read(card))

    def get_card(self, card_id: str) -> Result[CardRead, KanbanError]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            card = session.get(CardTable, card_id)
            if card is None:
                return Err(KanbanError.CARD_NOT_FOUND)
            return Ok(self._to_card_read(card))

    def update_card(
        self,
        card_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        column_id: str | None = None,
        position: int | None = None,
        priority: CardPriority | None = None,
        due_at: datetime | None | object = ...,
    ) -> Result[CardRead, KanbanError]:
        self._ensure_open()
        with Session(self._engine, expire_on_commit=False) as session:
            card = session.get(CardTable, card_id)
            if card is None:
                return Err(KanbanError.CARD_NOT_FOUND)

            old_col = card.column_id
            target_col = column_id if column_id is not None else old_col
            current_column = session.get(ColumnTable, old_col)
            target_column = session.get(ColumnTable, target_col)
            candidate = CardMoveCandidate(
                target_column_exists=target_column is not None,
                current_board_id=current_column.board_id if current_column else None,
                target_board_id=target_column.board_id if target_column else None,
            )
            if not TargetColumnExistsSpecification().is_satisfied_by(candidate):
                return Err(KanbanError.COLUMN_NOT_FOUND)
            if not SameBoardMoveSpecification().is_satisfied_by(candidate):
                return Err(KanbanError.INVALID_CARD_MOVE)

            if target_col != old_col:
                self._remove_card_and_renumber(session, old_col, card.id)
                if position is None:
                    target_cards = session.exec(
                        select(CardTable)
                        .where(
                            CardTable.column_id == target_col, CardTable.id != card.id
                        )
                        .order_by("position")
                    ).all()
                    card.column_id = target_col
                    card.position = len(target_cards)
                else:
                    self._insert_card_at(session, card, target_col, position)
            elif position is not None:
                self._move_within_column(session, card, position)

            if title is not None:
                card.title = title
            if description is not None:
                card.description = description
            if priority is not None:
                card.priority = priority.value
            if due_at is None or isinstance(due_at, datetime):
                card.due_at = due_at

            session.add(card)
            session.commit()
            session.refresh(card)
            return Ok(self._to_card_read(card))

    def _remove_card_and_renumber(
        self, session: Session, column_id: str, card_id: str
    ) -> None:
        remaining = session.exec(
            select(CardTable)
            .where(CardTable.column_id == column_id, CardTable.id != card_id)
            .order_by("position")
        ).all()
        for index, row in enumerate(remaining):
            row.position = index
            session.add(row)

    def _insert_card_at(
        self, session: Session, card: CardTable, column_id: str, requested_position: int
    ) -> None:
        others = session.exec(
            select(CardTable)
            .where(CardTable.column_id == column_id, CardTable.id != card.id)
            .order_by("position")
        ).all()
        position = min(max(0, requested_position), len(others))
        ordered = list(others[:position]) + [card] + list(others[position:])
        for index, row in enumerate(ordered):
            row.column_id = column_id
            row.position = index
            session.add(row)

    def _move_within_column(
        self, session: Session, card: CardTable, requested_position: int
    ) -> None:
        self._insert_card_at(session, card, card.column_id, requested_position)

    @staticmethod
    def _to_card_read(card: CardTable) -> CardRead:
        return CardRead(
            id=card.id,
            column_id=card.column_id,
            title=card.title,
            description=card.description,
            position=card.position,
            priority=CardPriority(card.priority),
            due_at=_ensure_utc(card.due_at) if card.due_at else None,
        )


class SQLiteKanbanRepository(SQLModelKanbanRepository):
    def __init__(self, db_path: str) -> None:
        super().__init__(sqlite_url_from_path(db_path))
