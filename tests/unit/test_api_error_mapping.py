from __future__ import annotations

import pytest
from fastapi import status

from src.api.routers._errors import (
    _APPLICATION_ERROR_HTTP_MAP,
    ApplicationHTTPException,
)
from src.application.shared import ApplicationError

pytestmark = pytest.mark.unit


def test_application_error_http_mapping_is_exhaustive() -> None:
    assert set(_APPLICATION_ERROR_HTTP_MAP) == set(ApplicationError)


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_type"),
    [
        (
            ApplicationError.BOARD_NOT_FOUND,
            status.HTTP_404_NOT_FOUND,
            "https://starter-template-fastapi.dev/problems/board-not-found",
        ),
        (
            ApplicationError.COLUMN_NOT_FOUND,
            status.HTTP_404_NOT_FOUND,
            "https://starter-template-fastapi.dev/problems/column-not-found",
        ),
        (
            ApplicationError.CARD_NOT_FOUND,
            status.HTTP_404_NOT_FOUND,
            "https://starter-template-fastapi.dev/problems/card-not-found",
        ),
        (
            ApplicationError.INVALID_CARD_MOVE,
            status.HTTP_409_CONFLICT,
            "https://starter-template-fastapi.dev/problems/invalid-card-move",
        ),
        (
            ApplicationError.PATCH_NO_CHANGES,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "https://starter-template-fastapi.dev/problems/patch-no-changes",
        ),
        (
            ApplicationError.UNMAPPED_DOMAIN_ERROR,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "https://starter-template-fastapi.dev/problems/internal-domain-error",
        ),
    ],
)
def test_application_http_exception_exposes_stable_machine_metadata(
    error: ApplicationError,
    expected_status: int,
    expected_type: str,
) -> None:
    exc = ApplicationHTTPException(error)

    assert exc.status_code == expected_status
    assert exc.detail == error.detail
    assert exc.code == error.value
    assert exc.type_uri == expected_type
