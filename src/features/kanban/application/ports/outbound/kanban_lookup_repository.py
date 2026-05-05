from __future__ import annotations

from typing import Protocol


class KanbanLookupRepositoryPort(Protocol):
    def find_board_id_by_card(self, card_id: str) -> str | None: ...

    def find_board_id_by_column(self, column_id: str) -> str | None: ...
