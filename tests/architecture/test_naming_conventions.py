from __future__ import annotations

import ast

import pytest

from tests.architecture.conftest import iter_python_modules, parse_module_ast

MARKER = pytest.mark.architecture


@MARKER
def test_port_protocol_names_end_with_port() -> None:
    """fastapi-hexagonal-architecture: Port names should communicate boundary role."""
    for path in iter_python_modules("src.application.ports"):
        tree = parse_module_ast(path)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                assert node.name.endswith("Port"), (
                    "fastapi-hexagonal-architecture: "
                    f"port class {node.name} in {path} must end with 'Port'"
                )


@MARKER
def test_outbound_adapter_names_match_conventions() -> None:
    """fastapi-hexagonal-architecture: Adapter names should communicate
    implementation role.
    """
    allowed_suffixes = (
        "Repository",
        "UnitOfWork",
        "Adapter",
        "View",
        "Mapper",
        "Table",
        "Clock",
        "IdGenerator",
    )
    for path in iter_python_modules("src.infrastructure.adapters.outbound"):
        tree = parse_module_ast(path)
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                if any(
                    isinstance(base, ast.Name) and base.id == "Protocol"
                    for base in node.bases
                ):
                    continue
                if node.name.endswith("Error"):
                    continue
                assert node.name.endswith(allowed_suffixes), (
                    "fastapi-hexagonal-architecture: "
                    f"adapter class {node.name} in {path} has invalid suffix"
                )
