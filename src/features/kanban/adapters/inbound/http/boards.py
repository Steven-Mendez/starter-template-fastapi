"""FastAPI routes for Kanban board resources.

Per-route ``require_authorization`` enforces ReBAC checks on the
``kanban`` resource type:

* ``POST /boards`` — no check; the use case writes the initial owner
  tuple from the actor.
* ``GET /boards`` — no check; the use case calls ``lookup_resources``
  to filter.
* ``GET /boards/{id}`` — ``read``.
* ``PATCH /boards/{id}`` — ``update``.
* ``DELETE /boards/{id}`` and ``POST /boards/{id}/restore`` — ``delete``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from src.features.kanban.adapters.inbound.http.dependencies import (
    ActorIdDep,
    CreateBoardUseCaseDep,
    DeleteBoardUseCaseDep,
    GetBoardUseCaseDep,
    ListBoardsUseCaseDep,
    PatchBoardUseCaseDep,
    RestoreBoardUseCaseDep,
)
from src.features.kanban.adapters.inbound.http.errors import (
    raise_http_from_application_error,
)
from src.features.kanban.adapters.inbound.http.mappers import (
    to_board_detail_response,
    to_board_summary_response,
    to_create_board_input,
    to_patch_board_input,
)
from src.features.kanban.adapters.inbound.http.schemas import (
    BoardCreate,
    BoardDetail,
    BoardSummary,
    BoardUpdate,
)
from src.features.kanban.application.commands import (
    CreateBoardCommand,
    DeleteBoardCommand,
    PatchBoardCommand,
    RestoreBoardCommand,
)
from src.features.kanban.application.queries import GetBoardQuery, ListBoardsQuery
from src.platform.api.authorization import require_authorization
from src.platform.shared.result import Err, Ok


def _board_id_from_path(request) -> str:  # type: ignore[no-untyped-def]
    """Resource-id loader that reads ``board_id`` from the path."""
    return str(request.path_params["board_id"])


boards_read_router = APIRouter(tags=["boards"])
boards_write_router = APIRouter(tags=["boards"])


@boards_write_router.post("/boards", status_code=status.HTTP_201_CREATED)
def create_board(
    body: BoardCreate,
    use_case: CreateBoardUseCaseDep,
    actor_id: ActorIdDep,
) -> BoardSummary:
    """Create a new board; the use case writes the initial owner tuple."""
    command = CreateBoardCommand(title=to_create_board_input(body), actor_id=actor_id)
    match use_case.execute(command):
        case Ok(value):
            return to_board_summary_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_read_router.get("/boards")
def list_boards(
    use_case: ListBoardsUseCaseDep,
    actor_id: ActorIdDep,
) -> list[BoardSummary]:
    """Return boards the calling user has at least ``read`` on."""
    match use_case.execute(ListBoardsQuery(actor_id=actor_id)):
        case Ok(value):
            return [to_board_summary_response(board) for board in value]
        case Err(err):
            raise_http_from_application_error(err)


@boards_read_router.get(
    "/boards/{board_id}",
    dependencies=[require_authorization("read", "kanban", _board_id_from_path)],
)
def get_board(board_id: UUID, use_case: GetBoardUseCaseDep) -> BoardDetail:
    """Return one board with its columns and cards expanded."""
    match use_case.execute(GetBoardQuery(board_id=str(board_id))):
        case Ok(value):
            return to_board_detail_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_write_router.patch(
    "/boards/{board_id}",
    dependencies=[require_authorization("update", "kanban", _board_id_from_path)],
)
def patch_board(
    board_id: UUID,
    body: BoardUpdate,
    use_case: PatchBoardUseCaseDep,
    actor_id: ActorIdDep,
) -> BoardSummary:
    """Apply a sparse update to a board and return the refreshed summary."""
    command = PatchBoardCommand(
        board_id=str(board_id),
        title=to_patch_board_input(body),
        actor_id=actor_id,
    )
    match use_case.execute(command):
        case Ok(value):
            return to_board_summary_response(value)
        case Err(err):
            raise_http_from_application_error(err)


@boards_write_router.delete(
    "/boards/{board_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_authorization("delete", "kanban", _board_id_from_path)],
)
def delete_board(
    board_id: UUID,
    use_case: DeleteBoardUseCaseDep,
    actor_id: ActorIdDep,
) -> None:
    """Soft-delete a board; reversible via ``POST /boards/{id}/restore``."""
    command = DeleteBoardCommand(board_id=str(board_id), actor_id=actor_id)
    match use_case.execute(command):
        case Ok(_):
            return
        case Err(err):
            raise_http_from_application_error(err)


@boards_write_router.post(
    "/boards/{board_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[require_authorization("delete", "kanban", _board_id_from_path)],
)
def restore_board(
    board_id: UUID,
    use_case: RestoreBoardUseCaseDep,
    actor_id: ActorIdDep,
) -> None:
    """Restore a previously soft-deleted board and its cascaded columns/cards."""
    command = RestoreBoardCommand(board_id=str(board_id), actor_id=actor_id)
    match use_case.execute(command):
        case Ok(_):
            return
        case Err(err):
            raise_http_from_application_error(err)
