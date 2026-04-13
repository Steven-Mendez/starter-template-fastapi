from __future__ import annotations

import pytest
from pydantic import ValidationError

from kanban.schemas import BoardCreate

pytestmark = pytest.mark.unit


def test_board_create_requires_non_empty_title() -> None:
    with pytest.raises(ValidationError):
        BoardCreate.model_validate({"title": ""})
