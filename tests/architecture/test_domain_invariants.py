from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

MARKER = pytest.mark.architecture


def _annotation_mentions_error_union(annotation: ast.AST) -> bool:
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        return _annotation_mentions_error_union(
            annotation.left
        ) or _annotation_mentions_error_union(annotation.right)
    if isinstance(annotation, ast.Name):
        return annotation.id in {"KanbanError", "ApplicationError"}
    if isinstance(annotation, ast.Attribute):
        return annotation.attr in {"KanbanError", "ApplicationError"}
    if isinstance(annotation, ast.Subscript):
        return _annotation_mentions_error_union(
            annotation.value
        ) or _annotation_mentions_error_union(annotation.slice)
    if isinstance(annotation, ast.Tuple):
        return any(_annotation_mentions_error_union(elt) for elt in annotation.elts)
    return False


@MARKER
def test_domain_methods_can_return_error_unions() -> None:
    """Domain methods may encode failures with Result[..., KanbanError]."""
    for path in iter_python_modules("src.domain.kanban.models"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.returns is not None:
                _ = _annotation_mentions_error_union(node.returns)


@MARKER
def test_application_kanban_errors_do_not_use_exception_mapping() -> None:
    errors_module = (
        Path(__file__).resolve().parents[2] / "src/application/kanban/errors.py"
    )
    parse_module_ast(errors_module)
    source = errors_module.read_text(encoding="utf-8")
    assert "_EXCEPTION_ERROR_MAP" not in source
    assert "from_domain_" + "exception" not in source
    assert "Kanban" + "DomainError" not in source
