from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_makefile_includes_quality_targets() -> None:
    content = (ROOT / "Makefile").read_text(encoding="utf-8")
    for target in ("lint:", "typecheck:", "test-fast:"):
        assert target in content


def test_ci_workflow_runs_quality_pipeline() -> None:
    workflow = ROOT / ".github" / "workflows" / "ci.yml"
    assert workflow.exists()
    content = workflow.read_text(encoding="utf-8")
    assert "make lint" in content
    assert "make typecheck" in content
    assert "make test-fast" in content
