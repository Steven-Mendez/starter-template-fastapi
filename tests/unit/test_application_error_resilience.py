from __future__ import annotations

import pytest

from src.application.shared import ApplicationError, from_domain_error
from src.application.shared import errors as app_errors
from src.domain.shared.errors import KanbanError

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("domain_error", "expected_app_error"),
    [
        (KanbanError.BOARD_NOT_FOUND, ApplicationError.BOARD_NOT_FOUND),
        (KanbanError.COLUMN_NOT_FOUND, ApplicationError.COLUMN_NOT_FOUND),
        (KanbanError.CARD_NOT_FOUND, ApplicationError.CARD_NOT_FOUND),
        (KanbanError.INVALID_CARD_MOVE, ApplicationError.INVALID_CARD_MOVE),
    ],
)
def test_from_domain_error_preserves_known_mappings(
    domain_error: KanbanError,
    expected_app_error: ApplicationError,
) -> None:
    assert from_domain_error(domain_error) is expected_app_error


def test_from_domain_error_returns_fallback_when_mapping_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    drifted_map = {
        key: value
        for key, value in app_errors._ERROR_MAP.items()
        if key is not KanbanError.INVALID_CARD_MOVE
    }
    monkeypatch.setattr(app_errors, "_ERROR_MAP", drifted_map)

    assert (
        from_domain_error(KanbanError.INVALID_CARD_MOVE)
        is ApplicationError.UNMAPPED_DOMAIN_ERROR
    )
