from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from kanban.errors import KanbanError
from kanban.result import Err, Ok, Result
from kanban.schemas import BoardDetail, BoardSummary, CardPriority, CardRead, ColumnRead


class SQLiteKanbanRepository:
    def __init__(self, db_path: str) -> None:
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS boards (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS columns_ (
                id TEXT PRIMARY KEY,
                board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                position INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cards (
                id TEXT PRIMARY KEY,
                column_id TEXT NOT NULL REFERENCES columns_(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                position INTEGER NOT NULL,
                priority TEXT NOT NULL,
                due_at TEXT
            );
            """
        )

    def is_ready(self) -> bool:
        try:
            self._conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def create_board(self, title: str) -> BoardSummary:
        board_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        with self._conn:
            self._conn.execute(
                "INSERT INTO boards (id, title, created_at) VALUES (?, ?, ?)",
                (board_id, title, created_at.isoformat()),
            )
        return BoardSummary(id=board_id, title=title, created_at=created_at)

    def list_boards(self) -> list[BoardSummary]:
        rows = self._conn.execute(
            "SELECT id, title, created_at FROM boards ORDER BY created_at ASC"
        ).fetchall()
        return [
            BoardSummary(
                id=cast(str, row["id"]),
                title=cast(str, row["title"]),
                created_at=datetime.fromisoformat(cast(str, row["created_at"])),
            )
            for row in rows
        ]

    def get_board(self, board_id: str) -> Result[BoardDetail, KanbanError]:
        board = self._conn.execute(
            "SELECT id, title, created_at FROM boards WHERE id = ?",
            (board_id,),
        ).fetchone()
        if board is None:
            return Err(KanbanError.BOARD_NOT_FOUND)

        columns = self._conn.execute(
            (
                "SELECT id, board_id, title, position "
                "FROM columns_ WHERE board_id = ? ORDER BY position ASC"
            ),
            (board_id,),
        ).fetchall()

        out_columns: list[ColumnRead] = []
        for col in columns:
            cards = self._conn.execute(
                (
                    "SELECT id, column_id, title, description, "
                    "position, priority, due_at "
                    "FROM cards WHERE column_id = ? ORDER BY position ASC"
                ),
                (cast(str, col["id"]),),
            ).fetchall()
            out_columns.append(
                ColumnRead(
                    id=cast(str, col["id"]),
                    board_id=cast(str, col["board_id"]),
                    title=cast(str, col["title"]),
                    position=cast(int, col["position"]),
                    cards=[self._row_to_card(card) for card in cards],
                )
            )

        return Ok(
            BoardDetail(
                id=cast(str, board["id"]),
                title=cast(str, board["title"]),
                created_at=datetime.fromisoformat(cast(str, board["created_at"])),
                columns=out_columns,
            )
        )

    def update_board(
        self, board_id: str, title: str
    ) -> Result[BoardSummary, KanbanError]:
        with self._conn:
            updated = self._conn.execute(
                "UPDATE boards SET title = ? WHERE id = ?",
                (title, board_id),
            )
        if updated.rowcount == 0:
            return Err(KanbanError.BOARD_NOT_FOUND)
        board = self._conn.execute(
            "SELECT id, title, created_at FROM boards WHERE id = ?",
            (board_id,),
        ).fetchone()
        assert board is not None
        return Ok(
            BoardSummary(
                id=cast(str, board["id"]),
                title=cast(str, board["title"]),
                created_at=datetime.fromisoformat(cast(str, board["created_at"])),
            )
        )

    def delete_board(self, board_id: str) -> Result[None, KanbanError]:
        with self._conn:
            deleted = self._conn.execute("DELETE FROM boards WHERE id = ?", (board_id,))
        if deleted.rowcount == 0:
            return Err(KanbanError.BOARD_NOT_FOUND)
        return Ok(None)

    def create_column(
        self, board_id: str, title: str
    ) -> Result[ColumnRead, KanbanError]:
        exists = self._conn.execute(
            "SELECT 1 FROM boards WHERE id = ?",
            (board_id,),
        ).fetchone()
        if exists is None:
            return Err(KanbanError.BOARD_NOT_FOUND)
        next_pos = self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM columns_ WHERE board_id = ?",
            (board_id,),
        ).fetchone()
        position = int(cast(int, next_pos[0])) if next_pos else 0
        column_id = str(uuid.uuid4())
        with self._conn:
            self._conn.execute(
                (
                    "INSERT INTO columns_ "
                    "(id, board_id, title, position) VALUES (?, ?, ?, ?)"
                ),
                (column_id, board_id, title, position),
            )
        return Ok(
            ColumnRead(
                id=column_id,
                board_id=board_id,
                title=title,
                position=position,
                cards=[],
            )
        )

    def delete_column(self, column_id: str) -> Result[None, KanbanError]:
        with self._conn:
            deleted = self._conn.execute(
                "DELETE FROM columns_ WHERE id = ?",
                (column_id,),
            )
        if deleted.rowcount == 0:
            return Err(KanbanError.COLUMN_NOT_FOUND)
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
        col = self._conn.execute(
            "SELECT id FROM columns_ WHERE id = ?",
            (column_id,),
        ).fetchone()
        if col is None:
            return Err(KanbanError.COLUMN_NOT_FOUND)
        next_pos = self._conn.execute(
            "SELECT COALESCE(MAX(position), -1) + 1 FROM cards WHERE column_id = ?",
            (column_id,),
        ).fetchone()
        position = int(cast(int, next_pos[0])) if next_pos else 0
        card_id = str(uuid.uuid4())
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO cards (
                    id, column_id, title, description, position, priority, due_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card_id,
                    column_id,
                    title,
                    description,
                    position,
                    priority.value,
                    due_at.isoformat() if due_at else None,
                ),
            )
        return Ok(
            CardRead(
                id=card_id,
                column_id=column_id,
                title=title,
                description=description,
                position=position,
                priority=priority,
                due_at=due_at,
            )
        )

    def get_card(self, card_id: str) -> Result[CardRead, KanbanError]:
        row = self._conn.execute(
            (
                "SELECT id, column_id, title, description, position, priority, due_at "
                "FROM cards WHERE id = ?"
            ),
            (card_id,),
        ).fetchone()
        if row is None:
            return Err(KanbanError.CARD_NOT_FOUND)
        return Ok(self._row_to_card(row))

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
        row = self._conn.execute(
            (
                "SELECT id, column_id, title, description, position, priority, due_at "
                "FROM cards WHERE id = ?"
            ),
            (card_id,),
        ).fetchone()
        if row is None:
            return Err(KanbanError.CARD_NOT_FOUND)

        current = self._row_to_card(row)
        old_col = current.column_id
        target_col = column_id or old_col

        target_exists = self._conn.execute(
            "SELECT board_id FROM columns_ WHERE id = ?",
            (target_col,),
        ).fetchone()
        if target_exists is None:
            return Err(KanbanError.COLUMN_NOT_FOUND)
        old_board = self._conn.execute(
            "SELECT board_id FROM columns_ WHERE id = ?",
            (old_col,),
        ).fetchone()
        if old_board is None:
            return Err(KanbanError.COLUMN_NOT_FOUND)
        if cast(str, old_board["board_id"]) != cast(str, target_exists["board_id"]):
            return Err(KanbanError.INVALID_CARD_MOVE)

        if target_col != old_col:
            self._remove_card_and_renumber(old_col, card_id)
            if position is None:
                next_pos = self._conn.execute(
                    (
                        "SELECT COALESCE(MAX(position), -1) + 1 "
                        "FROM cards WHERE column_id = ? AND id != ?"
                    ),
                    (target_col, card_id),
                ).fetchone()
                target_pos = int(cast(int, next_pos[0])) if next_pos else 0
            else:
                target_pos = position
            self._insert_card_at(card_id, target_col, target_pos)
        elif position is not None:
            self._insert_card_at(card_id, old_col, position)

        updates: list[str] = []
        values: list[object] = []
        if title is not None:
            updates.append("title = ?")
            values.append(title)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        if priority is not None:
            updates.append("priority = ?")
            values.append(priority.value)
        if due_at is None or isinstance(due_at, datetime):
            updates.append("due_at = ?")
            values.append(due_at.isoformat() if due_at else None)

        if updates:
            values.append(card_id)
            with self._conn:
                self._conn.execute(
                    f"UPDATE cards SET {', '.join(updates)} WHERE id = ?",
                    tuple(values),
                )
        return self.get_card(card_id)

    def _insert_card_at(
        self, card_id: str, column_id: str, requested_position: int
    ) -> None:
        cards = self._conn.execute(
            (
                "SELECT id FROM cards "
                "WHERE column_id = ? AND id != ? ORDER BY position ASC"
            ),
            (column_id, card_id),
        ).fetchall()
        ordered_ids = [cast(str, row["id"]) for row in cards]
        pos = min(max(0, requested_position), len(ordered_ids))
        ordered_ids.insert(pos, card_id)
        with self._conn:
            self._conn.execute(
                "UPDATE cards SET column_id = ? WHERE id = ?",
                (column_id, card_id),
            )
            for index, cid in enumerate(ordered_ids):
                self._conn.execute(
                    "UPDATE cards SET position = ? WHERE id = ?",
                    (index, cid),
                )

    def _remove_card_and_renumber(self, column_id: str, card_id: str) -> None:
        rows = self._conn.execute(
            (
                "SELECT id FROM cards "
                "WHERE column_id = ? AND id != ? ORDER BY position ASC"
            ),
            (column_id, card_id),
        ).fetchall()
        with self._conn:
            for index, row in enumerate(rows):
                self._conn.execute(
                    "UPDATE cards SET position = ? WHERE id = ?",
                    (index, cast(str, row["id"])),
                )

    @staticmethod
    def _row_to_card(row: sqlite3.Row) -> CardRead:
        due_raw = cast(str | None, row["due_at"])
        return CardRead(
            id=cast(str, row["id"]),
            column_id=cast(str, row["column_id"]),
            title=cast(str, row["title"]),
            description=cast(str | None, row["description"]),
            position=cast(int, row["position"]),
            priority=CardPriority(cast(str, row["priority"])),
            due_at=datetime.fromisoformat(due_raw) if due_raw else None,
        )
