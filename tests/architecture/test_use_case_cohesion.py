from __future__ import annotations

import ast

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

MARKER = pytest.mark.architecture


def _constructor_annotation_name(annotation: ast.expr | None) -> str:
    if annotation is None:
        return ""
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    if isinstance(annotation, ast.Subscript):
        return _constructor_annotation_name(annotation.value)
    if isinstance(annotation, ast.BinOp):
        return _constructor_annotation_name(
            annotation.left
        ) + _constructor_annotation_name(annotation.right)
    return ""


@MARKER
def test_use_case_modules_are_cohesive() -> None:
    """hexagonal-architecture-conformance: check-use-case-cohesion."""
    for path in iter_python_modules("src.application.use_cases"):
        tree = parse_module_ast(path)
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef)]
        assert len(classes) == 1, (
            f"hexagonal-architecture-conformance: {path} must define exactly one class"
        )
        cls = classes[0]
        assert cls.name.endswith("UseCase"), (
            "hexagonal-architecture-conformance: "
            f"{path} class {cls.name} must end with UseCase"
        )

        public_methods = [
            fn
            for fn in cls.body
            if isinstance(fn, ast.FunctionDef) and not fn.name.startswith("_")
        ]
        assert len(public_methods) == 1 and public_methods[0].name == "execute", (
            "hexagonal-architecture-conformance: "
            f"{path} class {cls.name} must expose only execute as public method"
        )

        init_methods = [
            fn
            for fn in cls.body
            if isinstance(fn, ast.FunctionDef) and fn.name == "__init__"
        ]
        if not init_methods:
            continue
        init_fn = init_methods[0]
        for arg in init_fn.args.args[1:]:
            symbol = _constructor_annotation_name(arg.annotation)
            assert symbol.endswith("Port") or symbol.endswith("UseCase"), (
                "hexagonal-architecture-conformance: "
                f"{path} constructor dependency {arg.arg} must be typed as "
                "*Port or *UseCase"
            )
