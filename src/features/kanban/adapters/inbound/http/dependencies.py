"""FastAPI dependency aliases that resolve Kanban use-case ports."""

from __future__ import annotations

from typing import Annotated, TypeAlias
from uuid import UUID

from fastapi import Depends, Request

from src.features.kanban.application.ports.inbound import (
    CheckReadinessUseCasePort,
    CreateBoardUseCasePort,
    CreateCardUseCasePort,
    CreateColumnUseCasePort,
    DeleteBoardUseCasePort,
    DeleteColumnUseCasePort,
    GetBoardUseCasePort,
    GetCardUseCasePort,
    ListBoardsUseCasePort,
    PatchBoardUseCasePort,
    PatchCardUseCasePort,
    RestoreBoardUseCasePort,
)
from src.features.kanban.composition.app_state import get_kanban_container
from src.platform.api.request_state import get_actor_id as _platform_get_actor_id


def _get_create_board(request: Request) -> CreateBoardUseCasePort:
    return get_kanban_container(request).create_board_use_case()


def _get_patch_board(request: Request) -> PatchBoardUseCasePort:
    return get_kanban_container(request).patch_board_use_case()


def _get_delete_board(request: Request) -> DeleteBoardUseCasePort:
    return get_kanban_container(request).delete_board_use_case()


def _get_restore_board(request: Request) -> RestoreBoardUseCasePort:
    return get_kanban_container(request).restore_board_use_case()


def _get_get_board(request: Request) -> GetBoardUseCasePort:
    return get_kanban_container(request).get_board_use_case()


def _get_list_boards(request: Request) -> ListBoardsUseCasePort:
    return get_kanban_container(request).list_boards_use_case()


def _get_create_column(request: Request) -> CreateColumnUseCasePort:
    return get_kanban_container(request).create_column_use_case()


def _get_delete_column(request: Request) -> DeleteColumnUseCasePort:
    return get_kanban_container(request).delete_column_use_case()


def _get_create_card(request: Request) -> CreateCardUseCasePort:
    return get_kanban_container(request).create_card_use_case()


def _get_patch_card(request: Request) -> PatchCardUseCasePort:
    return get_kanban_container(request).patch_card_use_case()


def _get_get_card(request: Request) -> GetCardUseCasePort:
    return get_kanban_container(request).get_card_use_case()


def _get_check_readiness(request: Request) -> CheckReadinessUseCasePort:
    return get_kanban_container(request).check_readiness_use_case()


CreateBoardUseCaseDep: TypeAlias = Annotated[
    CreateBoardUseCasePort, Depends(_get_create_board)
]
PatchBoardUseCaseDep: TypeAlias = Annotated[
    PatchBoardUseCasePort, Depends(_get_patch_board)
]
DeleteBoardUseCaseDep: TypeAlias = Annotated[
    DeleteBoardUseCasePort, Depends(_get_delete_board)
]
RestoreBoardUseCaseDep: TypeAlias = Annotated[
    RestoreBoardUseCasePort, Depends(_get_restore_board)
]
GetBoardUseCaseDep: TypeAlias = Annotated[GetBoardUseCasePort, Depends(_get_get_board)]
ListBoardsUseCaseDep: TypeAlias = Annotated[
    ListBoardsUseCasePort, Depends(_get_list_boards)
]
CreateColumnUseCaseDep: TypeAlias = Annotated[
    CreateColumnUseCasePort, Depends(_get_create_column)
]
DeleteColumnUseCaseDep: TypeAlias = Annotated[
    DeleteColumnUseCasePort, Depends(_get_delete_column)
]
CreateCardUseCaseDep: TypeAlias = Annotated[
    CreateCardUseCasePort, Depends(_get_create_card)
]
PatchCardUseCaseDep: TypeAlias = Annotated[
    PatchCardUseCasePort, Depends(_get_patch_card)
]
GetCardUseCaseDep: TypeAlias = Annotated[GetCardUseCasePort, Depends(_get_get_card)]
CheckReadinessUseCaseDep: TypeAlias = Annotated[
    CheckReadinessUseCasePort, Depends(_get_check_readiness)
]


def get_actor_id(request: Request) -> UUID | None:
    """Return the authenticated user's id stamped on ``request.state``.

    Auth's ``get_current_principal`` populates ``request.state.actor_id``;
    delegating to the platform getter keeps anonymous deployments (no auth dep
    wired) working — they get ``None``, which the audit columns accept.
    """
    return _platform_get_actor_id(request)


ActorIdDep: TypeAlias = Annotated[UUID | None, Depends(get_actor_id)]
