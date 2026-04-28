from __future__ import annotations

import ast
import inspect
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, get_args, get_origin, get_type_hints

import pytest
from fastapi.routing import APIRoute

from src.api import dependencies as api_dependencies
from src.api.routers import kanban_router, root_router
from src.application.commands import KanbanCommandHandlers, KanbanCommandInputPort
from src.application.ports import (
    KanbanCommandRepositoryPort,
    KanbanQueryRepositoryPort,
    KanbanRepositoryPort,
)
from src.application.queries import KanbanQueryHandlers, KanbanQueryInputPort
from src.application.shared.readiness import ReadinessProbe
from src.infrastructure.persistence.lifecycle import ClosableResource
from src.infrastructure.persistence.sqlmodel_repository import SQLModelKanbanRepository

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
RUNTIME_MODULE_FILES = ("main.py",)


@dataclass
class ImportDiagnostic:
    source_module: str
    target_import: str
    violated_rule: str
    transitive_path: list[str] | None = None

    def __str__(self) -> str:
        if self.transitive_path is None:
            return (
                f"{self.source_module} imports {self.target_import} "
                f"(Violation: {self.violated_rule})"
            )
        return (
            f"{self.source_module} transitively reaches {self.target_import} via "
            f"{' -> '.join(self.transitive_path)} (Violation: {self.violated_rule})"
        )


def parse_imports(file_path: Path) -> Set[str]:
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(file_path))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def get_module_imports() -> Dict[str, Set[str]]:
    modules: Dict[str, Set[str]] = {}

    for py_file in SRC_DIR.rglob("*.py"):
        rel_path = py_file.relative_to(ROOT)
        module_name = str(rel_path.with_suffix("")).replace("/", ".")
        modules[module_name] = parse_imports(py_file)

    for runtime_file in RUNTIME_MODULE_FILES:
        file_path = ROOT / runtime_file
        if file_path.exists():
            modules[file_path.stem] = parse_imports(file_path)

    return modules


def resolve_local_import_targets(
    import_name: str,
    known_modules: Set[str],
) -> Set[str]:
    if import_name in known_modules:
        return {import_name}

    prefix = f"{import_name}."
    direct_children = {
        module
        for module in known_modules
        if module.startswith(prefix) and module.count(".") == import_name.count(".") + 1
    }
    if direct_children:
        return direct_children

    return {module for module in known_modules if module.startswith(prefix)}


def build_local_dependency_graph(
    modules: Dict[str, Set[str]],
) -> Dict[str, Set[str]]:
    graph: Dict[str, Set[str]] = {name: set() for name in modules}
    known_modules = set(modules)

    for module_name, imports in modules.items():
        for imp in imports:
            graph[module_name].update(resolve_local_import_targets(imp, known_modules))

    return graph


def get_layer(module_name: str) -> str:
    if module_name.startswith("src.domain"):
        return "domain"
    if module_name.startswith("src.application"):
        return "application"
    if module_name.startswith("src.api"):
        return "api"
    if module_name.startswith("src.infrastructure"):
        return "infrastructure"
    if module_name == "main":
        return "runtime"
    return "other"


DENY_MATRIX = {
    "domain": [
        "src.domain.kanban.repository",
        "src.application",
        "src.api",
        "src.infrastructure",
        "fastapi",
        "sqlmodel",
        "sqlalchemy",
        "settings",
        "dependencies",
        "src.settings",
        "src.config",
    ],
    "application": [
        "src.domain.kanban.repository",
        "src.api",
        "src.infrastructure",
        "fastapi",
        "sqlmodel",
        "sqlalchemy",
        "settings",
        "dependencies",
        "src.settings",
        "src.config",
    ],
    "api": [
        "src.domain.kanban.repository",
        "src.domain",
        "src.infrastructure",
        "dependencies",
        "settings",
    ],
    "infrastructure": [
        "src.domain.kanban.repository",
        "src.api",
        "dependencies",
    ],
}

TRANSITIVE_DENY_MATRIX = {
    "domain": DENY_MATRIX["domain"],
    "application": DENY_MATRIX["application"],
    "api": [
        "src.domain.kanban.repository",
        "src.infrastructure",
        "dependencies",
        "settings",
    ],
    "infrastructure": DENY_MATRIX["infrastructure"],
}

EXTERNAL_LIBRARY_DENY = {
    "domain": [
        "fastapi",
        "starlette",
        "sqlmodel",
        "sqlalchemy",
        "uvicorn",
        "httpx",
        "alembic",
        "pydantic_settings",
        "psycopg",
    ],
    "application": [
        "fastapi",
        "starlette",
        "sqlmodel",
        "sqlalchemy",
        "uvicorn",
        "httpx",
        "alembic",
        "pydantic_settings",
        "psycopg",
    ],
    "api": ["sqlmodel", "sqlalchemy", "alembic", "uvicorn", "psycopg"],
    "infrastructure": [],
}


def check_direct_import_violations(
    modules: Dict[str, Set[str]],
) -> List[ImportDiagnostic]:
    diagnostics: list[ImportDiagnostic] = []

    for module_name, imports in modules.items():
        layer = get_layer(module_name)
        if layer in {"other", "runtime"}:
            continue

        denied_prefixes = DENY_MATRIX.get(layer, [])
        for imp in imports:
            for denied in denied_prefixes:
                if imp == denied or imp.startswith(f"{denied}."):
                    diagnostics.append(
                        ImportDiagnostic(
                            source_module=module_name,
                            target_import=imp,
                            violated_rule=f"Layer '{layer}' cannot import '{denied}'",
                        )
                    )

    return diagnostics


def shortest_path_to_denied_prefix(
    source_module: str,
    denied_prefix: str,
    graph: Dict[str, Set[str]],
) -> list[str] | None:
    queue: deque[tuple[str, list[str]]] = deque([(source_module, [source_module])])
    visited = {source_module}

    while queue:
        current, path = queue.popleft()
        for nxt in sorted(graph.get(current, set())):
            if nxt in visited:
                continue

            next_path = [*path, nxt]
            if nxt == denied_prefix or nxt.startswith(f"{denied_prefix}."):
                return next_path

            visited.add(nxt)
            queue.append((nxt, next_path))

    return None


def check_transitive_import_violations(
    modules: Dict[str, Set[str]],
    graph: Dict[str, Set[str]],
) -> List[ImportDiagnostic]:
    diagnostics: list[ImportDiagnostic] = []

    for module_name in sorted(modules):
        layer = get_layer(module_name)
        if layer in {"other", "runtime"}:
            continue

        for denied in TRANSITIVE_DENY_MATRIX.get(layer, []):
            path = shortest_path_to_denied_prefix(module_name, denied, graph)
            if path is None or len(path) <= 2:
                continue

            diagnostics.append(
                ImportDiagnostic(
                    source_module=module_name,
                    target_import=path[-1],
                    violated_rule=f"Layer '{layer}' transitively depends on '{denied}'",
                    transitive_path=path,
                )
            )

    return diagnostics


def check_architecture() -> List[ImportDiagnostic]:
    modules = get_module_imports()
    graph = build_local_dependency_graph(modules)
    diagnostics = check_direct_import_violations(modules)
    diagnostics.extend(check_transitive_import_violations(modules, graph))
    return diagnostics


def annotation_contains_type(annotation: object, expected: type[object]) -> bool:
    if annotation is expected:
        return True

    origin = get_origin(annotation)
    if origin is None:
        return False

    return any(annotation_contains_type(arg, expected) for arg in get_args(annotation))


def test_hexagonal_architecture_boundaries() -> None:
    diagnostics = check_architecture()
    if diagnostics:
        error_msgs = "\n".join(f" - {d}" for d in diagnostics)
        pytest.fail(f"Architecture boundary violations detected:\n{error_msgs}")


def test_forbidden_external_library_imports() -> None:
    modules = get_module_imports()
    violations: list[str] = []

    for module_name, imports in modules.items():
        layer = get_layer(module_name)
        if layer not in EXTERNAL_LIBRARY_DENY:
            continue

        for imp in imports:
            for forbidden in EXTERNAL_LIBRARY_DENY[layer]:
                if imp == forbidden or imp.startswith(f"{forbidden}."):
                    violations.append(
                        f"{module_name} imports {imp} "
                        f"(Violation: {layer} layer cannot import {forbidden})"
                    )

    if violations:
        pytest.fail(
            "External library forbidden import violations:\n"
            + "\n".join(f" - {violation}" for violation in sorted(violations))
        )


def test_domain_does_not_contain_port_modules() -> None:
    port_dir = SRC_DIR / "domain" / "kanban" / "repository"
    assert not port_dir.exists(), (
        "Repository ports must not live in the domain layer. "
        "Expected location: src/application/ports/"
    )


def test_domain_defines_board_summary_read_model() -> None:
    board_summary_model = SRC_DIR / "domain" / "kanban" / "models" / "board_summary.py"
    assert board_summary_model.exists()


def test_domain_kanban_services_package_removed() -> None:
    services_dir = SRC_DIR / "domain" / "kanban" / "services"
    assert not services_dir.exists()


def test_tests_do_not_import_legacy_domain_repository_module() -> None:
    violations: list[str] = []
    tests_dir = ROOT / "tests"

    for test_file in sorted(tests_dir.rglob("*.py")):
        tree = ast.parse(test_file.read_text(encoding="utf-8"), filename=str(test_file))
        has_legacy_import = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "src.domain.kanban.repository"
            for node in ast.walk(tree)
        )
        if has_legacy_import:
            violations.append(str(test_file.relative_to(ROOT)))

    assert not violations, (
        "Tests must import repository ports from src.application.ports: "
        + ", ".join(violations)
    )


def test_api_routes_use_cqrs_handlers() -> None:
    for route in kanban_router.routes:
        if not isinstance(route, APIRoute):
            continue

        endpoint = route.endpoint
        sig = inspect.signature(endpoint)
        type_hints = get_type_hints(endpoint, include_extras=True)

        has_query_port = False
        has_command_port = False
        has_concrete_query_handler = False
        has_concrete_command_handler = False
        has_repository = False

        for param_name, param in sig.parameters.items():
            annotation = type_hints.get(param_name, param.annotation)
            if annotation_contains_type(annotation, KanbanQueryInputPort):
                has_query_port = True
            if annotation_contains_type(annotation, KanbanCommandInputPort):
                has_command_port = True
            if annotation_contains_type(annotation, KanbanQueryHandlers):
                has_concrete_query_handler = True
            if annotation_contains_type(annotation, KanbanCommandHandlers):
                has_concrete_command_handler = True
            if annotation_contains_type(annotation, KanbanRepositoryPort):
                has_repository = True

        assert not has_repository, (
            f"Endpoint {endpoint.__name__} must not depend on a repository directly."
        )
        assert not has_concrete_query_handler, (
            f"Endpoint {endpoint.__name__} must depend on query ports, "
            "not concrete handlers."
        )
        assert not has_concrete_command_handler, (
            f"Endpoint {endpoint.__name__} must depend on command ports, "
            "not concrete handlers."
        )

        methods = route.methods or set()

        if "GET" in methods:
            assert has_query_port, (
                f"Read endpoint {endpoint.__name__} must use KanbanQueryInputPort."
            )
            assert not has_command_port, (
                f"Read endpoint {endpoint.__name__} must not use "
                "KanbanCommandInputPort."
            )
        else:
            assert has_command_port, (
                f"Write endpoint {endpoint.__name__} must use KanbanCommandInputPort."
            )
            assert not has_query_port, (
                f"Write endpoint {endpoint.__name__} must not use KanbanQueryInputPort."
            )


def test_api_schema_modules_do_not_import_application_contracts() -> None:
    modules = get_module_imports()
    diagnostics: list[str] = []

    for module_name, imports in modules.items():
        if not module_name.startswith("src.api.schemas"):
            continue

        leaked_imports = sorted(
            imp
            for imp in imports
            if imp == "src.application.contracts"
            or imp.startswith("src.application.contracts.")
        )
        diagnostics.extend(
            f"{module_name} imports {target}" for target in leaked_imports
        )

    if diagnostics:
        pytest.fail(
            "API schema modules must remain transport-owned:\n"
            + "\n".join(f" - {item}" for item in diagnostics)
        )


def test_persistence_adapters_match_repository_port_surface() -> None:
    port_methods = (
        {
            method_name
            for method_name, attr in KanbanCommandRepositoryPort.__dict__.items()
            if callable(attr) and not method_name.startswith("_")
        }
        | {
            method_name
            for method_name, attr in KanbanQueryRepositoryPort.__dict__.items()
            if callable(attr) and not method_name.startswith("_")
        }
        | {
            method_name
            for method_name, attr in ReadinessProbe.__dict__.items()
            if callable(attr) and not method_name.startswith("_")
        }
        | {
            method_name
            for method_name, attr in ClosableResource.__dict__.items()
            if callable(attr) and not method_name.startswith("_")
        }
    )

    diagnostics: list[str] = []
    for adapter in (SQLModelKanbanRepository,):
        adapter_methods = {
            method_name
            for method_name, attr in adapter.__dict__.items()
            if callable(attr) and not method_name.startswith("_")
        }
        extra_methods = sorted(adapter_methods - port_methods)
        if extra_methods:
            diagnostics.append(
                f"{adapter.__name__} exposes non-port methods: "
                f"{', '.join(extra_methods)}"
            )

    if diagnostics:
        pytest.fail(
            "Persistence adapters must not expose public methods "
            "outside driven ports:\n" + "\n".join(f" - {item}" for item in diagnostics)
        )


def test_api_dependencies_do_not_expose_repository_provider() -> None:
    assert not hasattr(api_dependencies, "get_kanban_repository")


def test_domain_aggregates_do_not_call_private_entity_methods() -> None:
    domain_models_dir = SRC_DIR / "domain" / "kanban" / "models"
    violations: list[str] = []

    for py_file in sorted(domain_models_dir.glob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        module_name = str(py_file.relative_to(ROOT).with_suffix("")).replace("/", ".")

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if not node.func.attr.startswith("_"):
                continue
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "self":
                continue

            receiver = ast.unparse(node.func.value)
            violations.append(
                f"{module_name}:{node.lineno} calls private method "
                f"{receiver}.{node.func.attr}()"
            )

    if violations:
        pytest.fail(
            "Domain aggregates/entities must not call private methods "
            "on other objects:\n" + "\n".join(f" - {item}" for item in violations)
        )


def test_api_dependencies_do_not_import_concrete_handler_classes() -> None:
    deps_file = SRC_DIR / "api" / "dependencies.py"
    tree = ast.parse(deps_file.read_text(encoding="utf-8"), filename=str(deps_file))

    violations: list[str] = []
    module_aliases: dict[str, str] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module == "src.application.commands":
                if any(alias.name == "KanbanCommandHandlers" for alias in node.names):
                    violations.append("src.application.commands.KanbanCommandHandlers")
            if node.module == "src.application.queries":
                if any(alias.name == "KanbanQueryHandlers" for alias in node.names):
                    violations.append("src.application.queries.KanbanQueryHandlers")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_aliases[alias.asname or alias.name] = alias.name

    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in {
            "KanbanCommandHandlers",
            "KanbanQueryHandlers",
        }:
            violations.append(node.id)

        if isinstance(node, ast.Attribute) and node.attr in {
            "KanbanCommandHandlers",
            "KanbanQueryHandlers",
        }:
            if isinstance(node.value, ast.Name):
                imported_module = module_aliases.get(node.value.id)
                if imported_module in {
                    "src.application.commands",
                    "src.application.queries",
                    "src.application.commands.handlers",
                    "src.application.queries.handlers",
                }:
                    violations.append(f"{imported_module}.{node.attr}")

    assert not violations, (
        "API dependencies must consume ports/factories, not concrete handlers: "
        + ", ".join(violations)
    )


def test_routes_do_not_inject_app_container_directly() -> None:
    for route in [*kanban_router.routes, *root_router.routes]:
        if not isinstance(route, APIRoute):
            continue

        endpoint = route.endpoint
        sig = inspect.signature(endpoint)
        type_hints = get_type_hints(endpoint, include_extras=True)

        for param_name, param in sig.parameters.items():
            annotation = type_hints.get(param_name, param.annotation)
            assert not annotation_contains_type(
                annotation, api_dependencies.AppContainer
            ), f"Endpoint {endpoint.__name__} must not inject AppContainer directly."


def _iter_route_dependency_calls(route: APIRoute) -> set[object]:
    calls: set[object] = set()
    stack = list(route.dependant.dependencies)

    while stack:
        dependency = stack.pop()
        calls.add(dependency.call)
        stack.extend(dependency.dependencies)

    return calls


def test_routes_do_not_depend_on_container_provider_callable() -> None:
    for route in [*kanban_router.routes, *root_router.routes]:
        if not isinstance(route, APIRoute):
            continue

        calls = _iter_route_dependency_calls(route)
        assert api_dependencies.get_app_container not in calls, (
            f"Route {route.path} must not depend on "
            "get_app_container as a route dependency."
        )


def test_legacy_root_wrappers_are_removed() -> None:
    assert not (ROOT / "dependencies.py").exists()
    assert not (ROOT / "settings.py").exists()


def test_di_composition_avoids_runtime_type_reflection() -> None:
    composition_file = SRC_DIR / "infrastructure" / "config" / "di" / "composition.py"
    tree = ast.parse(
        composition_file.read_text(encoding="utf-8"), filename=str(composition_file)
    )

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in {
            "isinstance",
            "getattr",
        }:
            violations.append(f"{node.func.id}() at line {node.lineno}")

    assert not violations, (
        "DI composition should be driven by typed ports, not runtime reflection: "
        + ", ".join(violations)
    )
