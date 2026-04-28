from __future__ import annotations

from typing import Annotated, TypeAlias

from fastapi import Depends, Request

from src.api.dependencies.security import get_app_container
from src.application.use_cases.board import (
    CreateBoardUseCase,
    DeleteBoardUseCase,
    GetBoardUseCase,
    ListBoardsUseCase,
    PatchBoardUseCase,
)
from src.application.use_cases.card import (
    CreateCardUseCase,
    GetCardUseCase,
    PatchCardUseCase,
)
from src.application.use_cases.column import CreateColumnUseCase, DeleteColumnUseCase
from src.application.use_cases.health.check_readiness import CheckReadinessUseCase


def get_create_board_use_case(request: Request) -> CreateBoardUseCase:
    container = get_app_container(request)
    return CreateBoardUseCase(
        uow=container.uow_factory(),
        id_gen=container.id_gen,
        clock=container.clock,
    )


def get_patch_board_use_case(request: Request) -> PatchBoardUseCase:
    container = get_app_container(request)
    return PatchBoardUseCase(uow=container.uow_factory())


def get_delete_board_use_case(request: Request) -> DeleteBoardUseCase:
    container = get_app_container(request)
    return DeleteBoardUseCase(uow=container.uow_factory())


def get_get_board_use_case(request: Request) -> GetBoardUseCase:
    container = get_app_container(request)
    return GetBoardUseCase(query_repository=container.query_repository)


def get_list_boards_use_case(request: Request) -> ListBoardsUseCase:
    container = get_app_container(request)
    return ListBoardsUseCase(query_repository=container.query_repository)


def get_create_column_use_case(request: Request) -> CreateColumnUseCase:
    container = get_app_container(request)
    return CreateColumnUseCase(uow=container.uow_factory(), id_gen=container.id_gen)


def get_delete_column_use_case(request: Request) -> DeleteColumnUseCase:
    container = get_app_container(request)
    return DeleteColumnUseCase(uow=container.uow_factory())


def get_create_card_use_case(request: Request) -> CreateCardUseCase:
    container = get_app_container(request)
    return CreateCardUseCase(uow=container.uow_factory(), id_gen=container.id_gen)


def get_patch_card_use_case(request: Request) -> PatchCardUseCase:
    container = get_app_container(request)
    return PatchCardUseCase(uow=container.uow_factory())


def get_get_card_use_case(request: Request) -> GetCardUseCase:
    container = get_app_container(request)
    return GetCardUseCase(query_repository=container.query_repository)


def get_check_readiness_use_case(request: Request) -> CheckReadinessUseCase:
    container = get_app_container(request)
    return CheckReadinessUseCase(readiness=container.readiness_probe)


CreateBoardUseCaseDep: TypeAlias = Annotated[
    CreateBoardUseCase,
    Depends(get_create_board_use_case),
]
PatchBoardUseCaseDep: TypeAlias = Annotated[
    PatchBoardUseCase,
    Depends(get_patch_board_use_case),
]
DeleteBoardUseCaseDep: TypeAlias = Annotated[
    DeleteBoardUseCase,
    Depends(get_delete_board_use_case),
]
GetBoardUseCaseDep: TypeAlias = Annotated[
    GetBoardUseCase,
    Depends(get_get_board_use_case),
]
ListBoardsUseCaseDep: TypeAlias = Annotated[
    ListBoardsUseCase,
    Depends(get_list_boards_use_case),
]
CreateColumnUseCaseDep: TypeAlias = Annotated[
    CreateColumnUseCase,
    Depends(get_create_column_use_case),
]
DeleteColumnUseCaseDep: TypeAlias = Annotated[
    DeleteColumnUseCase,
    Depends(get_delete_column_use_case),
]
CreateCardUseCaseDep: TypeAlias = Annotated[
    CreateCardUseCase,
    Depends(get_create_card_use_case),
]
PatchCardUseCaseDep: TypeAlias = Annotated[
    PatchCardUseCase,
    Depends(get_patch_card_use_case),
]
GetCardUseCaseDep: TypeAlias = Annotated[
    GetCardUseCase,
    Depends(get_get_card_use_case),
]
CheckReadinessUseCaseDep: TypeAlias = Annotated[
    CheckReadinessUseCase,
    Depends(get_check_readiness_use_case),
]
