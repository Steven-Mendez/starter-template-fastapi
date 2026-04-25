from __future__ import annotations

from typing import Protocol

from src.application.commands.board.create import CreateBoardCommand
from src.application.commands.board.delete import DeleteBoardCommand
from src.application.commands.board.patch import PatchBoardCommand
from src.application.commands.card.create import CreateCardCommand
from src.application.commands.card.patch import PatchCardCommand
from src.application.commands.column.create import CreateColumnCommand
from src.application.commands.column.delete import DeleteColumnCommand
from src.application.contracts import AppBoardSummary, AppCard, AppColumn
from src.application.shared import ApplicationError, AppResult


class KanbanCommandInputPort(Protocol):
    def handle_create_board(
        self, command: CreateBoardCommand
    ) -> AppResult[AppBoardSummary, ApplicationError]: ...

    def handle_patch_board(
        self, command: PatchBoardCommand
    ) -> AppResult[AppBoardSummary, ApplicationError]: ...

    def handle_delete_board(
        self, command: DeleteBoardCommand
    ) -> AppResult[None, ApplicationError]: ...

    def handle_create_column(
        self, command: CreateColumnCommand
    ) -> AppResult[AppColumn, ApplicationError]: ...

    def handle_delete_column(
        self, command: DeleteColumnCommand
    ) -> AppResult[None, ApplicationError]: ...

    def handle_create_card(
        self, command: CreateCardCommand
    ) -> AppResult[AppCard, ApplicationError]: ...

    def handle_patch_card(
        self,
        command: PatchCardCommand,
    ) -> AppResult[AppCard, ApplicationError]: ...
