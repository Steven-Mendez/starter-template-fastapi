from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.architecture.conftest import parse_module_ast

MARKER = pytest.mark.architecture


def _parse_review_checklist_bullets() -> list[str]:
    skill_path = (
        Path(__file__).resolve().parents[2]
        / ".opencode/skills/fastapi-hexagonal-architecture/SKILL.md"
    )
    lines = skill_path.read_text(encoding="utf-8").splitlines()
    start = lines.index("## Review Checklist") + 1
    end = lines.index("## Practical Import Checks")
    bullets: list[str] = []
    for line in lines[start:end]:
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
    return bullets


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _architecture_test_docstrings() -> list[str]:
    root = Path(__file__).resolve().parent
    docs: list[str] = []
    for path in sorted(root.glob("test_*.py")):
        tree = parse_module_ast(path)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                docs.append(ast.get_docstring(node) or "")
    return docs


@MARKER
def test_skill_review_checklist_has_architecture_test_coverage() -> None:
    """fastapi-hexagonal-architecture: check-skill-checklist-coverage."""
    bullets = _parse_review_checklist_bullets()
    docstrings = [doc.lower() for doc in _architecture_test_docstrings()]
    missing: list[str] = []
    for bullet in bullets:
        b = bullet.lower()
        slug = _slugify(bullet)
        covered = any(b in doc or slug in doc for doc in docstrings)
        if not covered:
            missing.append(bullet)
    assert not missing, (
        "fastapi-hexagonal-architecture: "
        f"review checklist bullets without architecture test coverage: {missing}"
    )


@MARKER
def test_skill_checklist_identifier_anchor() -> None:
    """fastapi-hexagonal-architecture: are-fastapi-routes-thin.

    does-the-domain-layer-avoid-fastapi-imports.
    does-the-domain-layer-avoid-sqlalchemy-imports.
    does-the-application-layer-avoid-fastapi-depends.
    does-the-application-layer-avoid-concrete-infrastructure.
    do-use-cases-depend-on-ports-rather-than-concrete-adapters.
    are-pydantic-api-schemas-kept-near-the-api-layer.
    are-sqlalchemy-models-kept-in-infrastructure.
    are-orm-models-separate-from-domain-entities-when-business-logic-is-meaningful.
    are-business-exceptions-translated-at-the-api-boundary.
    are-repositories-hiding-persistence-details.
    is-unit-of-work-used-when-transactions-matter.
    can-use-cases-run-with-fake-adapters.
    can-api-tests-override-fastapi-dependencies.
    are-ports-named-after-capabilities-rather-than-technologies.
    are-business-rules-in-domain-objects-or-domain-services.
    is-the-folder-structure-supporting-dependency-direction-rather-than-just-creating-many-folders.
    """
