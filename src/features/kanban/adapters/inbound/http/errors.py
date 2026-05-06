"""HTTP error mapping for Kanban application failures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import NoReturn

from fastapi import status

from src.features.kanban.application.errors import ApplicationError
from src.platform.api.error_handlers_app_exception import (
    ApplicationHTTPException as PlatformApplicationHTTPException,
)


@dataclass(frozen=True)
class _Contract:
    """Pair an HTTP status code with the Problem Details ``type`` URI for one error."""

    status_code: int
    type_uri: str


_APPLICATION_ERROR_HTTP_MAP: dict[ApplicationError, _Contract] = {
    ApplicationError.BOARD_NOT_FOUND: _Contract(
        status_code=status.HTTP_404_NOT_FOUND,
        type_uri="https://starter-template-fastapi.dev/problems/board-not-found",
    ),
    ApplicationError.COLUMN_NOT_FOUND: _Contract(
        status_code=status.HTTP_404_NOT_FOUND,
        type_uri="https://starter-template-fastapi.dev/problems/column-not-found",
    ),
    ApplicationError.CARD_NOT_FOUND: _Contract(
        status_code=status.HTTP_404_NOT_FOUND,
        type_uri="https://starter-template-fastapi.dev/problems/card-not-found",
    ),
    ApplicationError.INVALID_CARD_MOVE: _Contract(
        status_code=status.HTTP_409_CONFLICT,
        type_uri="https://starter-template-fastapi.dev/problems/invalid-card-move",
    ),
    ApplicationError.PATCH_NO_CHANGES: _Contract(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        type_uri="https://starter-template-fastapi.dev/problems/patch-no-changes",
    ),
    ApplicationError.UNMAPPED_DOMAIN_ERROR: _Contract(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        type_uri="https://starter-template-fastapi.dev/problems/internal-domain-error",
    ),
}


# Fail at import time if any new ApplicationError is added without a
# matching HTTP contract, instead of silently falling back to 500 at runtime.
if set(_APPLICATION_ERROR_HTTP_MAP) != set(ApplicationError):
    raise RuntimeError("ApplicationError to HTTP mapping is not exhaustive")


class KanbanApplicationHTTPException(PlatformApplicationHTTPException):
    """Kanban-specific :class:`ApplicationHTTPException` for an application error."""

    def __init__(self, error: ApplicationError) -> None:
        """Map ``error`` to its HTTP contract and forward to the platform exception."""
        contract = _APPLICATION_ERROR_HTTP_MAP[error]
        super().__init__(
            status_code=contract.status_code,
            detail=error.detail,
            code=error.value,
            type_uri=contract.type_uri,
        )
        self.error = error


def raise_http_from_application_error(err: ApplicationError) -> NoReturn:
    """Raise a Kanban HTTP exception from an :class:`ApplicationError`."""
    raise KanbanApplicationHTTPException(err)
