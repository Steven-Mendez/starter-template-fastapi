## Why

The codebase already passes every architecture test and import-linter contract for the
hexagonal-architecture skill (`./.opencode/skills/fastapi-hexagonal-architecture/SKILL.md`),
but three project-skeleton elements diverge from the literal recommendations of the skill
and leave dead surface inside the application boundary:

1. The FastAPI entrypoint lives at `./main.py`, not `src/main.py` as the skill's
   "main.py" section prescribes (lines 994 and 1012 of the SKILL).
2. `AppSettings` lives at `src/config/settings.py`, outside `src/infrastructure/`,
   contradicting the "Configuration" section of the skill (line 911 in the SKILL),
   which places `BaseSettings` inside infrastructure. The split also forces an extra
   `src.config` axis in the `pyproject.toml` import-linter contracts.
3. `src/application/ports/kanban_repository.py` declares `KanbanRepositoryPort`
   (a Protocol that aggregates `KanbanCommandRepositoryPort`,
   `KanbanQueryRepositoryPort`, and `KanbanLookupRepositoryPort`) but no use case,
   handler, or query in `src/application/` imports it. It is dead surface in the
   layer that is supposed to declare only what application needs.

Fixing these three structural deviations brings the project skeleton in line with
the canonical layout the skill prescribes, removes dead code from the application
port surface, and simplifies the import-linter configuration.

## What Changes

- Move `./main.py` to `src/main.py` and update every entrypoint that references it
  (`Dockerfile`, `docker-compose.yml`, `Makefile`, `README.md`, `pyproject.toml`
  `pythonpath`, any uvicorn invocation, alembic `env.py`, CI workflows).
- Move `src/config/settings.py` to `src/infrastructure/config/settings.py`,
  delete the now-empty `src/config/` package, update every import site
  (`src/api/dependencies/security.py`, `src/infrastructure/config/di/composition.py`,
  `src/infrastructure/config/di/container.py`, `main.py`/`src/main.py`), and remove
  `src.config` from the `pyproject.toml` import-linter `forbidden_modules` lists in
  the "Domain layer" and "Application layer" contracts (settings will then live
  under `src.infrastructure`, already forbidden from those sources).
- Delete `src/application/ports/kanban_repository.py` and remove the
  `KanbanRepositoryPort` symbol from `src/application/ports/__init__.py`. Update
  `src/infrastructure/adapters/outbound/persistence/sqlmodel/repository.py` so
  `_BaseSQLModelKanbanRepository` inherits the three segregated ports directly,
  and update `src/infrastructure/config/di/composition.py` so
  `ManagedKanbanRepositoryPort` composes the three segregated ports
  (plus `ReadinessProbe` and `ClosableResource`) instead of the aggregator. Adjust
  the affected unit/integration tests (`tests/unit/test_hexagonal_boundaries.py`).
- Add a new architecture test in `tests/architecture/` that fails if any
  `src.application.ports.*` Protocol inherits from more than one
  `*RepositoryPort`, locking the segregation in place.

No public HTTP API, database schema, domain model, application contract, or
runtime behaviour changes. This is a structural / dead-code change.

## Capabilities

### New Capabilities
- `hexagonal-architecture-conformance`: codifies the canonical project skeleton
  the FastAPI hexagonal skill prescribes (entrypoint location, configuration
  location, application port segregation), and the architecture tests that
  enforce it.

### Modified Capabilities
<!-- None. `openspec/specs/` is currently empty; this change introduces the
     conformance capability rather than modifying an existing one. -->

## Impact

- Affected code: `main.py` (moved), `src/config/` (removed), `src/infrastructure/config/settings.py` (new),
  `src/api/dependencies/security.py`, `src/infrastructure/config/di/composition.py`,
  `src/infrastructure/config/di/container.py`,
  `src/application/ports/kanban_repository.py` (removed),
  `src/application/ports/__init__.py`,
  `src/infrastructure/adapters/outbound/persistence/sqlmodel/repository.py`,
  `tests/unit/test_hexagonal_boundaries.py`,
  `tests/architecture/` (new test).
- Affected configuration: `pyproject.toml` (`pythonpath`, import-linter contracts),
  `Dockerfile`, `docker-compose.yml`, `Makefile`, `alembic.ini`/`alembic/env.py`,
  `.github/` workflows, `README.md`.
- No dependency changes.
- No HTTP, database, or domain behaviour changes — `tests/integration` and
  `tests/e2e` must remain green without modification.
- Breaking change for operators: any external script invoking
  `uvicorn main:app` must switch to `uvicorn src.main:app`. Mark as
  **BREAKING** for deployment tooling.
