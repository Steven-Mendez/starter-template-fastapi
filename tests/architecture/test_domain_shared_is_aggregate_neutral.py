from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture


def test_domain_shared_has_no_aggregate_specific_modules() -> None:
    root = Path(__file__).resolve().parents[2]
    domain_dir = root / "src/domain"
    aggregate_stems = {
        path.name.lower()
        for path in domain_dir.iterdir()
        if path.is_dir() and path.name != "shared"
    }
    for path in (domain_dir / "shared").rglob("*.py"):
        content = path.read_text(encoding="utf-8").lower()
        assert not any(stem in content for stem in aggregate_stems), (
            f"{path} leaks aggregate-specific naming"
        )
