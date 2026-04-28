from __future__ import annotations

import ast

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
def test_domain_methods_do_not_return_error_unions() -> None:
    """fastapi-hexagonal-architecture: Domain rule violations belong to typed domain
    exceptions, not return unions.
    """
    for path in iter_python_modules("src.domain.kanban.models"):
        tree = parse_module_ast(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.returns is not None:
                assert not _annotation_mentions_error_union(node.returns), (
                    "fastapi-hexagonal-architecture: "
                    f"domain invariant return type violated in {path}:{node.lineno}"
                )


@MARKER
def test_domain_exception_subclasses_have_translator_entries() -> None:
    """fastapi-hexagonal-architecture: Domain exception hierarchy must map at the
    application translation boundary.
    """
    exceptions_path = next(iter_python_modules("src.domain.kanban"))
    for candidate in iter_python_modules("src.domain.kanban"):
        if candidate.name == "exceptions.py":
            exceptions_path = candidate
            break

    exceptions_tree = parse_module_ast(exceptions_path)
    domain_exception_names: set[str] = set()
    for node in exceptions_tree.body:
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "KanbanDomainError":
                    domain_exception_names.add(node.name)

    errors_tree = parse_module_ast(next(iter_python_modules("src.application.shared")))
    for candidate in iter_python_modules("src.application.shared"):
        if candidate.name == "errors.py":
            errors_tree = parse_module_ast(candidate)
            break

    mapped_exception_names: set[str] = set()
    for node in errors_tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_EXCEPTION_ERROR_MAP":
                    if isinstance(node.value, ast.Dict):
                        for key in node.value.keys:
                            if isinstance(key, ast.Name):
                                mapped_exception_names.add(key.id)
        if isinstance(node, ast.AnnAssign):
            target = node.target
            if isinstance(target, ast.Name) and target.id == "_EXCEPTION_ERROR_MAP":
                if isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        if isinstance(key, ast.Name):
                            mapped_exception_names.add(key.id)

    missing = sorted(domain_exception_names - mapped_exception_names)
    assert not missing, (
        "fastapi-hexagonal-architecture: "
        "missing domain exception translator entries in "
        "src/application/shared/errors.py "
        f"for {', '.join(missing)}"
    )
