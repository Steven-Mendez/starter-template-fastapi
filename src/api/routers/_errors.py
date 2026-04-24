from __future__ import annotations

from typing import NoReturn

from fastapi import HTTPException, status

from src.application.shared import ApplicationError


def raise_http_from_application_error(err: ApplicationError) -> NoReturn:
    status_code = status.HTTP_404_NOT_FOUND
    if err is ApplicationError.INVALID_CARD_MOVE:
        status_code = status.HTTP_409_CONFLICT
    raise HTTPException(status_code=status_code, detail=err.detail)
