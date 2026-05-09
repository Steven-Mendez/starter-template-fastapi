"""Unit tests for the relaxed password complexity rule."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.features.auth.adapters.inbound.http.schemas import RegisterRequest

pytestmark = pytest.mark.unit


def _register(password: str) -> None:
    RegisterRequest(email="user@example.com", password=password)


def test_four_class_password_accepted() -> None:
    # Regression: every existing e2e test uses this password.
    _register("UserPassword123!")


def test_three_class_password_accepted() -> None:
    # New behaviour — uppercase + lowercase + digit, no symbol.
    _register("NoSymbolHere123")


def test_long_single_class_password_accepted() -> None:
    # New behaviour — 20+ chars bypasses the class-diversity check.
    _register("abcdefghijklmnopqrst")


def test_short_low_diversity_password_rejected() -> None:
    # 12 chars but only one class → still rejected by the new rule.
    with pytest.raises(ValidationError, match="at least 3 of"):
        _register("alllowercase")


def test_two_class_short_password_rejected() -> None:
    # Length under 20 with only two classes → rejected.
    with pytest.raises(ValidationError, match="at least 3 of"):
        _register("LowerAndUpper")
