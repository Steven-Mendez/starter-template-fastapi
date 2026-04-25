from __future__ import annotations

from dataclasses import dataclass

from src.application.commands.board.create import CreateBoardCommand, handle_create_board
from src.application.commands.board.delete import DeleteBoardCommand, handle_delete_board
from src.application.commands.board.patch import PatchBoardCommand, handle_patch_board
from src.application.commands.card.create import CreateCardCommand, handle_create_card
from src.application.commands.card.patch import PatchCardCommand, handle_patch_card
from src.application.commands.column.create import (
    CreateColumnCommand,
    handle_create_column,
)
from src.application.commands.column.delete import (
    DeleteColumnCommand,
    handle_delete_column,
)
from src.application.commands.port import KanbanCommandInputPort
from src.application.contracts import AppBoardSummary, AppCard, AppColumn
from src.application.ports.clock import Clock
from src.application.ports.id_generator import IdGenerator
from src.application.shared import ApplicationError, AppResult, UnitOfWork


@dataclass(slots=True)
class KanbanCommandHandlers(KanbanCommandInputPort):
    uow: UnitOfWork
    id_gen: IdGenerator
    clock: Clock

    def handle_create_board(
        self, command: CreateBoardCommand
    ) -> AppResult[AppBoardSummary, ApplicationError]:
        return handle_create_board(
            uow=self.uow,
            id_gen=self.id_gen,
            clock=self.clock,
            command=command,
        )

    def handle_patch_board(
        self, command: PatchBoardCommand
    ) -> AppResult[AppBoardSummary, ApplicationError]:
        return handle_patch_board(
            uow=self.uow,
            command=command,
        )

    def handle_delete_board(
        self, command: DeleteBoardCommand
    ) -> AppResult[None, ApplicationError]:
        return handle_delete_board(
            uow=self.uow,
            command=command,
        )

    def handle_create_column(
        self, command: CreateColumnCommand
    ) -> AppResult[AppColumn, ApplicationError]:
        return handle_create_column(
            uow=self.uow,
            id_gen=self.id_gen,
            command=command,
        )

    def handle_delete_column(
        self, command: DeleteColumnCommand
    ) -> AppResult[None, ApplicationError]:
        return handle_delete_column(
            uow=self.uow,
            command=command,
        )

    def handle_create_card(
        self, command: CreateCardCommand
    ) -> AppResult[AppCard, ApplicationError]:
        return handle_create_card(
            uow=self.uow,
            id_gen=self.id_gen,
            command=command,
        )

    def handle_patch_card(
        self,
        command: PatchCardCommand,
    ) -> AppResult[AppCard, ApplicationError]:
        return handle_patch_card(
            uow=self.uow,
            command=command,
        )
