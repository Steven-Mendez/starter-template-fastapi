# Proposal: Relocate Repository Ports to the Application Layer

**Change ID**: `relocate-ports-to-application-layer`
**Priority**: Critical
**Status**: Proposed

---

## Problem Statement

Repository port protocols (`KanbanCommandRepositoryPort`, `KanbanQueryRepositoryPort`, `KanbanRepositoryPort`) currently live under `src/domain/kanban/repository/`. In hexagonal architecture, **ports are contracts the application layer declares** to express what it needs from the outside world. They belong in `src/application/ports/`, not inside `src/domain/`.

Placing ports in the domain creates two concrete violations:

1. **Inverted dependency direction in the domain.** The domain package implicitly says "I know there is a repository interface that will implement me." The domain should know nothing about repositories or persistence.
2. **Infrastructure leaks into the domain namespace.** `src/infrastructure/persistence/sqlmodel_repository.py` imports `from src.domain.kanban.repository import KanbanRepositoryPort`. This means infrastructure depends on domain — correct — but that import resolves through a domain path, muddying the layer boundary and making dependency analysis harder.

The root cause is a structural naming choice made early in the project that treats ports as domain-owned concepts. Per the `hex-design-guide.md` dependency rule: `application code depends on domain code and port interfaces`. The ports are the application's declared needs, not the domain's.

---

## Rationale

- **Hexagonal architecture contracts**: ports live in the application ring so they can be defined in terms of domain objects without the domain owning the port definition.
- **Testability**: application-layer ports make it unambiguous where to put fake adapters in tests.
- **Dependency legibility**: `from src.application.ports.kanban_repository import KanbanCommandRepositoryPort` communicates ownership clearly. Any reader knows infrastructure must implement this application contract.
- **Enforcement**: the existing boundary test (`test_hexagonal_boundaries.py`) currently has to whitelist domain paths in deny matrices because infrastructure legitimately imports from `src.domain.kanban.repository`. After relocation, that exception disappears.

---

## Scope

**In scope:**
- Move `src/domain/kanban/repository/base.py` → `src/application/ports/kanban_repository.py` (consolidated).
- Move `src/domain/kanban/repository/command.py` → `src/application/ports/kanban_command_repository.py`.
- Move `src/domain/kanban/repository/query.py` → `src/application/ports/kanban_query_repository.py`.
- Update all import sites across `src/application/`, `src/infrastructure/`, `tests/`.
- Update the hexagonal boundary test's deny matrix to remove the domain repository path from infrastructure-allowed imports.
- Update `docs/architecture.md`.

**Out of scope:**
- Changing port method signatures (covered by a separate change).
- Moving `src/domain/kanban/models/` (domain entities stay in domain).
- Changing `src/domain/shared/` (shared domain types stay in domain).

---

## Affected Modules

| File | Change |
|---|---|
| `src/domain/kanban/repository/base.py` | Removed |
| `src/domain/kanban/repository/command.py` | Removed |
| `src/domain/kanban/repository/query.py` | Removed |
| `src/domain/kanban/repository/__init__.py` | Removed |
| `src/application/ports/__init__.py` | Added |
| `src/application/ports/kanban_command_repository.py` | Added |
| `src/application/ports/kanban_query_repository.py` | Added |
| `src/application/ports/kanban_repository.py` | Added (combined port) |
| `src/application/shared/unit_of_work.py` | Modified (import update) |
| `src/application/commands/handlers.py` | Modified (import update) |
| `src/application/queries/handlers.py` | Modified (import update) |
| `src/infrastructure/persistence/in_memory_repository.py` | Modified (import update) |
| `src/infrastructure/persistence/sqlmodel_repository.py` | Modified (import update) |
| `src/infrastructure/config/di/composition.py` | Modified (import update) |
| `tests/unit/test_hexagonal_boundaries.py` | Modified (deny matrix update) |
| `tests/unit/test_kanban_repository_contract.py` | Modified (import update) |
| `tests/unit/test_kanban_store.py` | Modified (imports `KanbanRepositoryPort as KanbanStore` from domain) |
| `tests/unit/conftest.py` | Modified (imports `KanbanRepositoryPort` from domain) |
| `tests/conftest.py` | Modified (type-annotates `kanban_store` fixture with `KanbanRepositoryPort` from domain) |
| `docs/architecture.md` | Modified |

---

## Proposed Change

After this change, the application layer owns all port definitions:

```
src/
  application/
    ports/
      __init__.py
      kanban_command_repository.py   # KanbanCommandRepositoryPort (Protocol)
      kanban_query_repository.py     # KanbanQueryRepositoryPort (Protocol)
      kanban_repository.py           # KanbanRepositoryPort (combined Protocol)
  domain/
    kanban/
      models/                        # unchanged
      specifications/                # unchanged
      # repository/ directory removed
```

Infrastructure implements application ports, as required by hexagonal architecture:

```
infrastructure imports: application ports, domain models
application imports: domain models, ports (self-owned)
domain imports: standard library only
```

---

## Acceptance Criteria

1. No Python file under `src/domain/` defines a Protocol class named `*RepositoryPort` or `*Port`.
2. All `*RepositoryPort` Protocols live under `src/application/ports/`.
3. `src/infrastructure/persistence/` imports repository ports from `src.application.ports`, not from `src.domain`.
4. `tests/unit/test_hexagonal_boundaries.py` passes without any exemptions for `src.domain.kanban.repository` in deny matrices.
5. All existing tests continue to pass after the refactor.
6. `docs/architecture.md` accurately reflects the new port locations.

---

## Migration Strategy

1. Create `src/application/ports/` directory with `__init__.py`.
2. Copy port Protocol definitions from `src/domain/kanban/repository/` to the new locations.
3. In each new port file, preserve the Protocol method signatures exactly.
4. Update imports in all consumers (application, infrastructure, tests) via a project-wide find-and-replace.
5. Delete `src/domain/kanban/repository/` directory.
6. Run the full test suite to confirm zero regressions.
7. Update the deny matrix in `test_hexagonal_boundaries.py` to disallow `src.domain.kanban.repository` anywhere.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Circular import if ports import domain models | Ports import from `src.domain.kanban.models` — domain-to-application direction is valid. Verify no reverse imports are introduced. |
| Large number of import sites to update | Use project-wide search-and-replace; the boundary test will catch any missed update. |
| `__init__.py` re-exports could be missed | Enumerate all `__init__.py` files in `src/domain/kanban/repository/` and trace what they re-export. |

---

## Test Strategy

- After relocation, run `python -m pytest tests/unit/test_hexagonal_boundaries.py -v` to confirm architecture rules pass.
- Run `python -m pytest tests/` to confirm no import errors or functional regressions.
- Add an assertion to `test_hexagonal_boundaries.py` that `src.domain.kanban.repository` does not exist as a module (file system check).
