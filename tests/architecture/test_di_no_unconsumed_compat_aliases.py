from __future__ import annotations

from pathlib import Path

import pytest

from tests.architecture.conftest import iter_python_modules

pytestmark = pytest.mark.architecture


def test_di_has_no_backward_compatible_markers() -> None:
    violations: list[str] = []
    root = Path(__file__).resolve().parents[2]
    for path in iter_python_modules("src.infrastructure.config.di"):
        rel = path.relative_to(root)
        source = path.read_text(encoding="utf-8").lower()
        if "backward-compatible" in source or "backward compatible" in source:
            violations.append(str(rel))

    assert not violations, "\n".join(violations)
