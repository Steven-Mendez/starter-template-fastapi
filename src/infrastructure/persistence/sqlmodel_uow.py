from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import TracebackType
from typing import Self

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from src.application.shared.unit_of_work import UnitOfWork
from src.domain.kanban.models import Board, BoardSummary
from src.domain.kanban.repository.command import KanbanCommandRepository
from src.domain.shared.errors import KanbanError
from src.domain.shared.result import Err, Ok, Result
from src.infrastructure.persistence.sqlmodel.models import (
    BoardTable,
    CardTable,
    ColumnTable,
)


class SqlModelCommandRepository(KanbanCommandRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def close(self) -> None:
        pass

    def create_board(self, title: str) -> BoardSummary:
        board = BoardTable(
            id=str(uuid.uuid4()),
            title=title,
            created_at=datetime.now(timezone.utc),
        )
        self._session.add(board)
        return BoardSummary(
            id=board.id,
            title=board.title,
            created_at=board.created_at,
        )

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]:
        board = self._session.get(BoardTable, board_id)
        if board is None:
            return Err(KanbanError.BOARD_NOT_FOUND)
        board.title = title
        self._session.add(board)
        return Ok(
            BoardSummary(
                id=board.id,
                title=board.title,
                created_at=board.created_at,
            )
        )

    def delete_board(self, board_id: str) -> Result[None, KanbanError]:
        board = self._session.get(BoardTable, board_id)
        if board is None:
            return Err(KanbanError.BOARD_NOT_FOUND)
        self._session.delete(board)
        return Ok(None)

    def get_board(self, board_id: str) -> Result[Board, KanbanError]:
        # Reuse logic from sqlmodel_repository but with self._session
        board = self._session.get(BoardTable, board_id)
        if board is None:
            return Err(KanbanError.BOARD_NOT_FOUND)

        columns = self._session.exec(
            select(ColumnTable)
            .where(ColumnTable.board_id == board_id)
            .order_by("position")
        ).all()

        from src.domain.kanban.models import Card, CardPriority, Column

        def _ensure_utc(dt: datetime) -> datetime:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt

        out_columns: list[Column] = []
        for column in columns:
            cards = self._session.exec(
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
                    cards=[
                        Card(
                            id=card.id,
                            column_id=card.column_id,
                            title=card.title,
                            description=card.description,
                            position=card.position,
                            priority=CardPriority(card.priority),
                            due_at=_ensure_utc(card.due_at) if card.due_at else None,
                        )
                        for card in cards
                    ],
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

    def save_board(self, board: Board) -> Result[None, KanbanError]:
        db_board = self._session.get(BoardTable, board.id)
        if db_board is None:
            return Err(KanbanError.BOARD_NOT_FOUND)
        db_board.title = board.title
        self._session.add(db_board)

        # Sync aggregate
        existing_cols = self._session.exec(
            select(ColumnTable).where(ColumnTable.board_id == board.id)
        ).all()
        existing_col_ids = {c.id for c in existing_cols}
        current_col_ids = {c.id for c in board.columns}
        for cid in existing_col_ids - current_col_ids:
            col_to_del = self._session.get(ColumnTable, cid)
            if col_to_del:
                self._session.delete(col_to_del)

        for column in board.columns:
            col_tbl = self._session.get(ColumnTable, column.id)
            if not col_tbl:
                col_tbl = ColumnTable(
                    id=column.id,
                    board_id=board.id,
                    title=column.title,
                    position=column.position,
                )
            else:
                col_tbl.title = column.title
                col_tbl.position = column.position
            self._session.add(col_tbl)

        # Delete board orphan cards
        existing_board_cards = self._session.exec(
            select(CardTable).join(ColumnTable).where(ColumnTable.board_id == board.id)
        ).all()
        existing_board_card_ids = {c.id for c in existing_board_cards}

        current_board_card_ids = {c.id for col in board.columns for c in col.cards}
        for cid in existing_board_card_ids - current_board_card_ids:
            card_to_del = self._session.get(CardTable, cid)
            if card_to_del:
                self._session.delete(card_to_del)

        for column in board.columns:
            for card in column.cards:
                card_tbl = self._session.get(CardTable, card.id)
                if not card_tbl:
                    card_tbl = CardTable(
                        id=card.id,
                        column_id=column.id,
                        title=card.title,
                        description=card.description,
                        position=card.position,
                        priority=card.priority.value,
                        due_at=card.due_at,
                    )
                else:
                    card_tbl.column_id = column.id
                    card_tbl.title = card.title
                    card_tbl.description = card.description
                    card_tbl.position = card.position
                    card_tbl.priority = card.priority.value
                    card_tbl.due_at = card.due_at
                self._session.add(card_tbl)
        return Ok(None)

    def get_board_id_for_card(self, card_id: str) -> str | None:
        card = self._session.get(CardTable, card_id)
        if not card:
            return None
        col = self._session.get(ColumnTable, card.column_id)
        if not col:
            return None
        return col.board_id

    def get_board_id_for_column(self, column_id: str) -> str | None:
        col = self._session.get(ColumnTable, column_id)
        if not col:
            return None
        return col.board_id


class SqlModelUnitOfWork(UnitOfWork):
    def __init__(self, engine: Engine):
        self._engine = engine
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = Session(self._engine, expire_on_commit=False)
        self.kanban = SqlModelCommandRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if self._session:
            if exc_type is not None:
                self._session.rollback()
            self._session.close()

    def commit(self) -> None:
        if self._session:
            self._session.commit()

    def rollback(self) -> None:
        if self._session:
            self._session.rollback()
