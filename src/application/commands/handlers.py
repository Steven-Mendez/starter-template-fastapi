from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.application.commands.create_board import CreateBoardCommand
from src.application.commands.create_card import CreateCardCommand
from src.application.commands.create_column import CreateColumnCommand
from src.application.commands.delete_board import DeleteBoardCommand
from src.application.commands.delete_column import DeleteColumnCommand
from src.application.commands.patch_board import PatchBoardCommand
from src.application.commands.patch_card import PatchCardCommand
from src.application.commands.port import KanbanCommandPort
from src.application.contracts import (
    AppBoardSummary,
    AppCard,
    AppColumn,
)
from src.application.contracts.mappers import (
    to_app_board_summary,
    to_app_card,
    to_app_column,
    to_domain_priority,
)
from src.application.shared import (
    AppErr,
    ApplicationError,
    AppOk,
    AppResult,
    UnitOfWork,
)
from src.application.shared.errors import from_domain_error
from src.domain.kanban.models import Card, Column
from src.domain.shared.result import Err, Ok


@dataclass(slots=True)
class KanbanCommandHandlers(KanbanCommandPort):
    uow: UnitOfWork

    def handle_create_board(self, command: CreateBoardCommand) -> AppBoardSummary:
        with self.uow:
            summary = self.uow.kanban.create_board(command.title)
            self.uow.commit()
            return to_app_board_summary(summary)

    def handle_patch_board(
        self, command: PatchBoardCommand
    ) -> AppResult[AppBoardSummary, ApplicationError]:
        with self.uow:
            result = self.uow.kanban.update_board(command.board_id, command.title)
            if isinstance(result, Ok):
                self.uow.commit()
                return AppOk(to_app_board_summary(result.value))
            return AppErr(from_domain_error(result.error))

    def handle_delete_board(
        self, command: DeleteBoardCommand
    ) -> AppResult[None, ApplicationError]:
        with self.uow:
            result = self.uow.kanban.delete_board(command.board_id)
            if isinstance(result, Ok):
                self.uow.commit()
                return AppOk(None)
            return AppErr(from_domain_error(result.error))

    def handle_create_column(
        self, command: CreateColumnCommand
    ) -> AppResult[AppColumn, ApplicationError]:
        with self.uow:
            board_result = self.uow.kanban.get_board(command.board_id)
            if isinstance(board_result, Err):
                return AppErr(from_domain_error(board_result.error))
            board = board_result.value

            max_pos = max((c.position for c in board.columns), default=-1)
            column = Column(
                id=str(uuid.uuid4()),
                board_id=command.board_id,
                title=command.title,
                position=max_pos + 1,
            )
            board.columns.append(column)

            save_err = self.uow.kanban.save_board(board)
            if isinstance(save_err, Err):
                return AppErr(from_domain_error(save_err.error))

            self.uow.commit()
            return AppOk(to_app_column(column))

    def handle_delete_column(
        self, command: DeleteColumnCommand
    ) -> AppResult[None, ApplicationError]:
        with self.uow:
            board_id = self.uow.kanban.find_board_id_by_column(command.column_id)
            if not board_id:
                return AppErr(ApplicationError.COLUMN_NOT_FOUND)

            board_result = self.uow.kanban.get_board(board_id)
            if isinstance(board_result, Err):
                return AppErr(from_domain_error(board_result.error))
            board = board_result.value

            delete_error = board.delete_column(command.column_id)
            if delete_error is not None:
                return AppErr(from_domain_error(delete_error))

            save_err = self.uow.kanban.save_board(board)
            if isinstance(save_err, Err):
                return AppErr(from_domain_error(save_err.error))

            self.uow.commit()
            return AppOk(None)

    def handle_create_card(
        self, command: CreateCardCommand
    ) -> AppResult[AppCard, ApplicationError]:
        with self.uow:
            board_id = self.uow.kanban.find_board_id_by_column(command.column_id)
            if not board_id:
                return AppErr(ApplicationError.COLUMN_NOT_FOUND)

            board_result = self.uow.kanban.get_board(board_id)
            if isinstance(board_result, Err):
                return AppErr(from_domain_error(board_result.error))
            board = board_result.value

            col = board.get_column(command.column_id)
            if not col:
                return AppErr(ApplicationError.COLUMN_NOT_FOUND)

            card = Card(
                id=str(uuid.uuid4()),
                column_id=command.column_id,
                title=command.title,
                description=command.description,
                position=0,  # will be recalculated by insert_card
                priority=to_domain_priority(command.priority),
                due_at=command.due_at,
            )
            col.insert_card(card)

            save_err = self.uow.kanban.save_board(board)
            if isinstance(save_err, Err):
                return AppErr(from_domain_error(save_err.error))

            self.uow.commit()
            return AppOk(to_app_card(card))

    def handle_patch_card(
        self,
        command: PatchCardCommand,
    ) -> AppResult[AppCard, ApplicationError]:
        with self.uow:
            board_id = self.uow.kanban.find_board_id_by_card(command.card_id)
            if not board_id:
                return AppErr(ApplicationError.CARD_NOT_FOUND)

            board_result = self.uow.kanban.get_board(board_id)
            if isinstance(board_result, Err):
                return AppErr(from_domain_error(board_result.error))
            board = board_result.value

            # If user wants to move the card
            if command.column_id is not None or command.position is not None:
                source_col = next(
                    (
                        c
                        for c in board.columns
                        if any(ca.id == command.card_id for ca in c.cards)
                    ),
                    None,
                )
                if source_col:
                    target_col_id = (
                        command.column_id
                        if command.column_id is not None
                        else source_col.id
                    )
                    err = board.move_card(
                        command.card_id, source_col.id, target_col_id, command.position
                    )
                    if err:
                        return AppErr(from_domain_error(err))

            # Update scalar fields
            updated_card = None
            for col in board.columns:
                for card in col.cards:
                    if card.id == command.card_id:
                        if command.title is not None:
                            card.title = command.title
                        if command.description is not None:
                            card.description = command.description
                        if command.priority is not None:
                            card.priority = to_domain_priority(command.priority)
                        if command.due_at_provided:
                            card.due_at = command.due_at
                        updated_card = card
                        break

            if not updated_card:
                return AppErr(ApplicationError.CARD_NOT_FOUND)

            save_err = self.uow.kanban.save_board(board)
            if isinstance(save_err, Err):
                return AppErr(from_domain_error(save_err.error))

            self.uow.commit()
            return AppOk(to_app_card(updated_card))
