# Design: Add Python Architecture Linting

**Change ID**: `add-python-architecture-linting`

---

## Tool Selection

### Primary tool: Import Linter

**Import Linter** (`import-linter`, PyPI) is selected as the primary static architecture enforcement tool.

**Why Import Linter:**
- Defines contracts declaratively in `pyproject.toml` — visible to all tooling without reading test code
- Runs as a standalone CLI (`lint-imports`) completely independent of pytest
- Catches violations at lint time, not test time — 30-second feedback loop vs. minutes
- Enforces both internal module direction AND external library forbidden imports when `include_external_packages = true`
- Produces clear violation messages: `src.application.commands.handlers → src.infrastructure.persistence.sqlmodel_repository (Forbidden: application layer cannot import infrastructure)`
- Maintained and well-documented; used by Django and other large Python projects
- Uses Grimp internally — no need to add Grimp as a separate dependency

**Why NOT standalone Grimp:**
Import Linter is built on Grimp and exposes it through its contract DSL. Adding Grimp separately would duplicate effort without adding enforcement capability.

**Why NOT Pylint or Flake8 plugins:**
- Ruff already handles style-level AST rules and is configured
- The pytest boundary checker handles structural/behavioral rules that AST plugins cannot (route handler injection type inspection, protocol surface parity)
- Custom Pylint plugins require maintaining plugin code; Import Linter contracts are configuration, not code

### Complementary tool: Existing pytest boundary checker (kept and enhanced)

The existing `test_hexagonal_boundaries.py` enforces structural and behavioral rules that Import Linter cannot:

| Rule | Import Linter | Pytest checker |
|---|---|---|
| Module dependency direction | ✅ | ✅ (redundant for safety) |
| Forbidden external library imports (fastapi in domain) | ✅ | ❌ |
| Route handler injects port, not concrete class | ❌ | ✅ |
| Adapter public surface matches port | ❌ | ✅ |
| Routes don't expose AppContainer directly | ❌ | ✅ |
| DI composition avoids runtime reflection | ❌ | ✅ |
| File-system constraints (directory doesn't exist) | ❌ | ✅ |

Import Linter and the pytest checker are complementary. Running both is intentional — violations caught by one are not caught by the other.

---

## Layer Mapping

### After all architecture OpenSpec changes are applied:

| Python module prefix | Hexagonal layer | Import Linter role |
|---|---|---|
| `src.domain.*` | Domain (innermost) | Source in isolation contracts |
| `src.application.*` | Application (ports + use cases + contracts) | Source in isolation contracts |
| `src.api.*` | Inbound adapter (FastAPI) | Source in adapter restriction contracts |
| `src.infrastructure.*` | Outbound adapter | Source in adapter restriction contracts |
| `src.config.*` | Configuration utility | Excluded from layer contracts; forbidden in domain/application |
| `main` | Composition root | Excluded from all contracts |
| `alembic.*` | Migration runner | Excluded from all contracts |
| `tests.*` | Test code | Excluded from all contracts |

### Dependency direction (permitted):

```
src.api         →  src.application (use cases, contracts, shared)
src.application →  src.domain      (entities, value objects, shared)
src.infrastructure → src.application (ports)
src.infrastructure → src.domain    (entities, value objects)
src.infrastructure → src.config    (settings)
main            →  src.api, src.infrastructure, src.config  (composition root, unrestricted)
```

### Dependency direction (forbidden):

```
src.domain      →  src.application, src.api, src.infrastructure, src.config
src.domain      →  fastapi, starlette, sqlmodel, sqlalchemy, uvicorn, httpx, alembic, pydantic_settings
src.application →  src.api, src.infrastructure, src.config
src.application →  fastapi, starlette, sqlmodel, sqlalchemy, uvicorn, httpx, alembic, pydantic_settings
src.api         →  src.infrastructure, src.domain (direct)
src.api         →  sqlmodel, sqlalchemy, alembic, uvicorn
src.infrastructure → src.api
```

---

## Import Linter Contract Design

All contracts live in `pyproject.toml` under `[tool.importlinter]`. Each contract has a `name` field that is human-readable. Comments above each contract block reference the `hex-design-guide.md` section that justifies the rule.

### Root configuration

```toml
[tool.importlinter]
root_packages = ["src"]
include_external_packages = true
# exclude_type_checking = true  # set if TYPE_CHECKING blocks cause false positives
```

`include_external_packages = true` is required so that contracts can forbid `fastapi`, `sqlmodel`, etc., not just `src.*` modules.

### Contract 1 — Domain layer: no outward or framework dependencies

Covers hex-design-guide.md §3 (Domain layer), §16 (Good dependency direction Rule 1), §29 (Rule 1).

```toml
# hex-design-guide.md §3, §16, §29 Rule 1
# "Domain code depends on almost nothing."
# "Domain has no framework imports."
[[tool.importlinter.contracts]]
name = "Domain layer: no outward or framework dependencies"
type = "forbidden"
source_modules = ["src.domain"]
forbidden_modules = [
    "src.application",
    "src.api",
    "src.infrastructure",
    "src.config",
    # Framework and infrastructure libraries
    "fastapi",
    "starlette",
    "sqlmodel",
    "sqlalchemy",
    "uvicorn",
    "httpx",
    "alembic",
    "pydantic_settings",
    # psycopg is a database driver — forbidden in domain
    "psycopg",
]
```

### Contract 2 — Application layer: no infrastructure or framework dependencies

Covers hex-design-guide.md §4 (Application layer), §16 (Rule 2), §29 (Rule 2).

```toml
# hex-design-guide.md §4, §16, §29 Rule 2
# "Application code depends on domain code and port interfaces."
# "Application has no database imports."
# Note: pydantic is intentionally NOT forbidden here.
# hex-design-guide.md §35 allows Pydantic for simple application DTOs.
[[tool.importlinter.contracts]]
name = "Application layer: no infrastructure or framework dependencies"
type = "forbidden"
source_modules = ["src.application"]
forbidden_modules = [
    "src.api",
    "src.infrastructure",
    "src.config",
    # Framework and infrastructure libraries
    "fastapi",
    "starlette",
    "sqlmodel",
    "sqlalchemy",
    "uvicorn",
    "httpx",
    "alembic",
    "pydantic_settings",
    "psycopg",
]
```

### Contract 3 — API adapter: no infrastructure bypass or direct domain access

Covers hex-design-guide.md §7 (FastAPI as inbound adapter), §8 (Pydantic schemas at edge), §16.

```toml
# hex-design-guide.md §7, §8, §16
# "FastAPI should be treated as a driving adapter."
# "API translates, it does not decide."
# Note: src.domain is forbidden — API must use src.application.contracts.
# Note: sqlmodel/sqlalchemy/alembic are infrastructure concerns; API must not use them.
[[tool.importlinter.contracts]]
name = "API adapter: no infrastructure bypass or direct domain access"
type = "forbidden"
source_modules = ["src.api"]
forbidden_modules = [
    "src.infrastructure",
    "src.domain",
    "sqlmodel",
    "sqlalchemy",
    "alembic",
    "uvicorn",
    "psycopg",
]
```

### Contract 4 — Infrastructure: no inbound adapter imports

Covers hex-design-guide.md §6 (Adapters), §16.

```toml
# hex-design-guide.md §6, §16
# "Infrastructure depends on application/domain contracts."
# Infrastructure must not import from the API adapter layer.
# It CAN import from src.application (ports), src.domain (entities), src.config.
[[tool.importlinter.contracts]]
name = "Infrastructure: no inbound adapter imports"
type = "forbidden"
source_modules = ["src.infrastructure"]
forbidden_modules = [
    "src.api",
]
```

### Contract 5 — Core inward dependency direction (layers contract)

Covers hex-design-guide.md §1 (The main idea: "Dependencies point inward").

```toml
# hex-design-guide.md §1
# "Dependencies point inward."
# Enforces: domain cannot import application; application cannot import api.
# Infrastructure is intentionally excluded — it sits beside, not above, the API layer.
[[tool.importlinter.contracts]]
name = "Core inward dependency direction"
type = "layers"
layers = [
    "src.api",
    "src.application",
    "src.domain",
]
```

> **Note**: The `layers` contract enforces that `src.api` can import `src.application` and `src.domain`, `src.application` can import `src.domain`, but the reverse is forbidden. It does not cover `src.infrastructure` (which is handled by Contracts 1–4).

---

## Handling Existing Violations

### Current state (before `relocate-ports-to-application-layer`)

Two files violate Contract 2:
- `src.application.queries.handlers` imports `src.domain.kanban.repository` (domain path, not application ports)
- `src.application.shared.unit_of_work` imports `src.domain.kanban.repository.command`

**Strategy**: Apply `relocate-ports-to-application-layer` BEFORE `add-python-architecture-linting`. After relocation, these imports become `src.application.ports.*` which is fully within the application layer — no violation.

### If `add-python-architecture-linting` must be applied before port relocation

Use `ignore_imports` in contracts to temporarily exclude known violations:

```toml
[[tool.importlinter.contracts]]
name = "Application layer: no infrastructure or framework dependencies"
type = "forbidden"
source_modules = ["src.application"]
forbidden_modules = [...]
# TODO: remove these when relocate-ports-to-application-layer is applied
ignore_imports = [
    "src.application.queries.handlers -> src.domain.kanban.repository",
    "src.application.shared.unit_of_work -> src.domain.kanban.repository.command",
]
```

Each `ignore_imports` entry must have a corresponding comment explaining which OpenSpec change will remove it and what the expected timeline is.

---

## Handling False Positives

### Legitimate cross-layer imports that might trigger false positives

| Pattern | Concern | Resolution |
|---|---|---|
| `src.infrastructure.*.py` imports `src.application.contracts` | After `relocate-boardsummary-read-model`, infrastructure imports `AppBoardSummary` from application | **Not a false positive** — infrastructure importing application contracts is explicitly allowed |
| `src.infrastructure.config.di.*` imports `src.application.commands`, `src.application.queries` | Composition root wires handlers | **Not a false positive** — infrastructure → application is allowed |
| `src.api.dependencies` imports `src.config` indirectly (through AppSettings type) | Config used in API adapter | Contract 3 forbids `src.infrastructure`, not `src.config`. **Not a false positive** |
| `TYPE_CHECKING` block imports | Used for type annotations to avoid circular imports | Add `exclude_type_checking = true` to root config if triggered |

### Dealing with `src.config` in `src.infrastructure`

`src.infrastructure.config.di.composition` imports `src.config.settings`. This is correct and intentional — infrastructure reads settings to wire adapters. Contract 4 does NOT forbid `src.config` from infrastructure. No exception needed.

---

## Handling Tests, Migrations, and the Composition Root

| Module | Treatment |
|---|---|
| `tests.*` | Excluded from contracts automatically (not in `root_packages = ["src"]`) |
| `alembic.*` | Excluded from contracts automatically (not in root package) |
| `main.py` | Excluded from contracts (not in `root_packages`) |
| `src.infrastructure.config.di.*` | Not excluded — and correctly passes all contracts since it imports from application/domain, not from api |

---

## Forbidden Import Enhancement to Pytest Boundary Checker

Import Linter handles external library detection via contracts. However, the existing pytest boundary checker currently has no external library check. Add the following test to complement Import Linter (serves as a verifiable test, not just a lint check):

```python
# tests/unit/test_hexagonal_boundaries.py (addition)

EXTERNAL_LIBRARY_DENY = {
    "domain": ["fastapi", "starlette", "sqlmodel", "sqlalchemy", "uvicorn", "httpx",
               "alembic", "pydantic_settings", "psycopg"],
    "application": ["fastapi", "starlette", "sqlmodel", "sqlalchemy", "uvicorn", "httpx",
                    "alembic", "pydantic_settings", "psycopg"],
    "api": ["sqlmodel", "sqlalchemy", "alembic", "uvicorn", "psycopg"],
    "infrastructure": [],  # infrastructure can import ORM, HTTP, etc.
}

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
            + "\n".join(f" - {v}" for v in sorted(violations))
        )
```

---

## Makefile Integration

```makefile
# Architectural dependency contracts (Import Linter)
lint-arch: ## Check Hexagonal Architecture import contracts
    uv run lint-imports

# Updated check target
check: lint lint-arch typecheck ## Run lint + architecture lint + type checks
```

---

## Pre-commit Integration

```yaml
# .pre-commit-config.yaml (addition)
- repo: local
  hooks:
    - id: architecture-lint
      name: architecture lint (import-linter)
      entry: uv run lint-imports
      language: system
      pass_filenames: false
      types: [python]
```

---

## CI Integration

```yaml
# .github/workflows/ci.yml (addition)
- name: Architecture lint
  run: make lint-arch
```

Position: between `Lint` and `Typecheck` steps. Architecture lint does not depend on typecheck output, so it can run in any order with respect to mypy.

---

## How to Add a New Port or Adapter Without Breaking Contracts

This section becomes part of `docs/architecture.md`.

### Adding a new port

1. Create the port Protocol in `src/application/ports/<name>.py`.
2. The port may import from `src.domain.*` and `src.application.contracts` (both allowed).
3. Run `make lint-arch` — no new violations if the port file only imports from allowed modules.

### Adding a new outbound adapter

1. Create the adapter in `src/infrastructure/<name>.py`.
2. The adapter may import from `src.application.ports`, `src.domain.*`, and any infrastructure library (`sqlmodel`, `httpx`, etc.).
3. The adapter must NOT import from `src.api.*` (Contract 4 will catch this).
4. Run `make lint-arch` — no new violations if the adapter respects Contract 4.

### Adding a new inbound adapter (new driver)

1. Create the adapter in a new package (e.g., `src/cli/`, `src/consumer/`).
2. Add the new package prefix to the `source_modules` list in Contract 3 if identical rules apply.
3. The adapter may import from `src.application.*` (use cases, ports, contracts).
4. The adapter must NOT import from `src.infrastructure.*` (same rule as `src.api`).
5. Run `make lint-arch` — no violations if the adapter respects the boundary.

### Adding a new domain entity

1. Create the entity in `src/domain/<bounded_context>/`.
2. The entity must import only from stdlib and `src.domain.*`.
3. Run `make lint-arch` — no violations if no external imports are added.

---

## Mapping to `hex-design-guide.md`

| Guide Section | Rule | Contract |
|---|---|---|
| §1 "Dependencies point inward" | Domain←application reverse is forbidden | Contract 5 (layers) |
| §3 "Domain should not know about FastAPI, SQLAlchemy..." | Domain cannot import framework libs | Contract 1 |
| §4 "Application should not directly use SQLAlchemy, httpx, FastAPI Request" | Application cannot import infrastructure libs | Contract 2 |
| §16 "Bad: domain → infrastructure" | Domain cannot import src.infrastructure | Contract 1 |
| §16 "Bad: application → FastAPI" | Application cannot import fastapi | Contract 2 |
| §16 "Bad: application → SQLAlchemy" | Application cannot import sqlalchemy | Contract 2 |
| §29 Rule 1 "Domain has no framework imports" | Verified by Contract 1 + pytest check | Contract 1 + pytest |
| §29 Rule 2 "Application has no database imports" | Verified by Contract 2 + pytest check | Contract 2 + pytest |
| §7 "FastAPI as an inbound adapter" | API cannot bypass to infrastructure | Contract 3 |
| §6 "Adapter implements a port" | Infrastructure cannot import from API | Contract 4 |

---

## Rules That Cannot Be Fully Automated by Import Linter

The following rules from the guide require the existing pytest boundary checker or code review:

| Rule | Why Not Automatable by Imports |
|---|---|
| "Use cases are callable without FastAPI" (§29 Rule 3) | Requires inspecting constructor signatures and type annotations — pytest checker |
| "API translates, it does not decide" (§29 Rule 5) | Requires behavioral analysis — code review |
| "Route endpoints use port types, not concrete handlers" | Requires type annotation inspection — pytest checker |
| "Adapter public surface matches port" | Requires Protocol structural comparison — pytest checker |
| "Routes don't inject AppContainer directly" | Requires FastAPI dependency graph inspection — pytest checker |
