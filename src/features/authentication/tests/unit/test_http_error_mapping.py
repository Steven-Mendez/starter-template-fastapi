"""Unit tests for auth error to HTTP mapping exhaustiveness."""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from src.features.authentication.adapters.inbound.http.errors import (
    EXPLICIT_AUTH_ERROR_TYPES,
    raise_http_from_auth_error,
)
from src.features.authentication.application.errors import (
    AuthError,
    InactiveUserError,
    PermissionDeniedError,
)

pytestmark = pytest.mark.unit


def _all_subclasses(cls: type[AuthError]) -> set[type[AuthError]]:
    found: set[type[AuthError]] = set()
    for subclass in cls.__subclasses__():
        found.add(subclass)
        found.update(_all_subclasses(subclass))
    return found


def test_all_auth_errors_are_explicitly_mapped() -> None:
    assert set(EXPLICIT_AUTH_ERROR_TYPES) == _all_subclasses(AuthError)


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_detail"),
    [
        (
            InactiveUserError("Inactive user"),
            status.HTTP_403_FORBIDDEN,
            "Account inactive",
        ),
        (
            PermissionDeniedError("Not enough permissions"),
            status.HTTP_403_FORBIDDEN,
            "Permission denied",
        ),
    ],
)
def test_security_errors_map_to_403(
    exc: AuthError,
    expected_status: int,
    expected_detail: str,
) -> None:
    with pytest.raises(HTTPException) as raised:
        raise_http_from_auth_error(exc)

    assert raised.value.status_code == expected_status
    assert raised.value.detail == expected_detail
