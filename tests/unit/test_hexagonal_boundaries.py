from __future__ import annotations

import ast
import inspect
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, get_args, get_origin, get_type_hints

import pytest
from fastapi.routing import APIRoute

from src.api.kanban_router import kanban_router
from src.application.commands import KanbanCommandHandlers
from src.application.queries import KanbanQueryHandlers
from src.domain.kanban.repository import KanbanRepository

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
RUNTIME_MODULE_FILES = (
    "dependencies.py",
    "main.py",
    "problem_details.py",
    "settings.py",
)


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
    if module_name in {"dependencies", "main", "problem_details", "settings"}:
        return "runtime"
    return "other"


DENY_MATRIX = {
    "domain": [
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
        "src.infrastructure",
        "dependencies",
        "settings",
    ],
    "infrastructure": [
        "src.api",
        "dependencies",
    ],
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

        for denied in DENY_MATRIX.get(layer, []):
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


def test_api_routes_use_cqrs_handlers() -> None:
    for route in kanban_router.routes:
        if not isinstance(route, APIRoute):
            continue

        endpoint = route.endpoint
        sig = inspect.signature(endpoint)
        type_hints = get_type_hints(endpoint, include_extras=True)

        has_query_handler = False
        has_command_handler = False
        has_repository = False

        for param_name, param in sig.parameters.items():
            annotation = type_hints.get(param_name, param.annotation)
            if annotation_contains_type(annotation, KanbanQueryHandlers):
                has_query_handler = True
            if annotation_contains_type(annotation, KanbanCommandHandlers):
                has_command_handler = True
            if annotation_contains_type(annotation, KanbanRepository):
                has_repository = True

        assert not has_repository, (
            f"Endpoint {endpoint.__name__} must not depend on a repository directly."
        )

        methods = route.methods or set()

        if "GET" in methods:
            assert has_query_handler, (
                f"Read endpoint {endpoint.__name__} must use KanbanQueryHandlers."
            )
            assert not has_command_handler, (
                f"Read endpoint {endpoint.__name__} must not use KanbanCommandHandlers."
            )
        else:
            assert has_command_handler, (
                f"Write endpoint {endpoint.__name__} must use KanbanCommandHandlers."
            )
            assert not has_query_handler, (
                f"Write endpoint {endpoint.__name__} must not use KanbanQueryHandlers."
            )
