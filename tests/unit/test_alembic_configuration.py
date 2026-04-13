from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_alembic_ini_exists() -> None:
    assert Path("alembic.ini").exists()


def test_alembic_env_uses_sqlmodel_metadata() -> None:
    env_py = Path("alembic/env.py")
    assert env_py.exists()
    content = env_py.read_text(encoding="utf-8")
    assert "get_sqlmodel_metadata" in content
    assert "target_metadata = get_sqlmodel_metadata()" in content
