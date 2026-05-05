## Why

This repository is a starter template; consumers will copy it and add new business features on top. The current layer-first layout (`src/{api,application,domain,infrastructure}`) makes it hard to know "what belongs to a feature" and forces edits across four directories per feature. The hexagonal-architecture skill explicitly recommends a feature-first layout where everything about a bounded context lives in one folder. The Kanban example must become the canonical reference of how to build a feature, including the boundary between feature and shared platform code, inbound/outbound port Protocols, FastAPI best practices, and conformance contracts.

## What Changes

- **BREAKING**: Move all production code under `src/features/<feature>/{domain,application,adapters,composition}` and a new `src/platform/` shared kernel. The current `src/{api,application,domain,infrastructure}` directories are removed.
- Introduce `src/platform/` for cross-feature concerns: settings, app factory, error handlers, request middleware, logging config, persistence engine wiring, readiness, shared kernel (`Result`, `ClockPort`, `IdGeneratorPort`, default adapters).
- Migrate Kanban into `src/features/kanban/` as the canonical example with full hex layout: `domain/`, `application/{ports/{inbound,outbound},commands,queries,contracts,errors,use_cases}`, `adapters/{inbound/http,outbound/{persistence,query}}`, `composition/`.
- Add **inbound port Protocols** (one per use case) so HTTP adapters depend on abstractions, not concrete use case classes.
- Per-feature **composition root** (`features/kanban/composition/wiring.py`) registered from `src/main.py`.
- Rewrite **import-linter contracts** to enforce: feature-internal layering, no cross-feature imports, platform never imports features, tests scoped to their feature.
- Apply **FastAPI best practices**: remove redundant `response_model=` where the return type already matches, move `require_write_api_key` to router-level `dependencies=[...]` for write operations, eliminate double-tagging in nested routers, add `[tool.fastapi]` entrypoint and switch dev/run scripts to `fastapi dev`/`fastapi run`, type `AppSettings` properly (eliminate `Any`).
- Move `get_app_container` out of `security.py` into a dedicated `dependencies/container.py` module under `platform/`.
- Update `alembic.ini`/`env.py` to point at the new module locations for SQLModel metadata.

## Capabilities

### New Capabilities
- `feature-layout`: Defines the canonical filesystem layout, naming, and module organization rules for any feature in this template (kanban is the reference implementation).
- `platform-shared-kernel`: Defines the `src/platform/` package and what code is allowed to live there (settings, app factory, middleware, error handlers, persistence engine, shared ports/adapters reusable across features).
- `kanban-feature`: The Kanban bounded context: domain (Board/Column/Card), application use cases, ports, contracts, HTTP/persistence adapters, composition.
- `inbound-ports`: Inbound port Protocol-per-use-case convention: where they live, naming, and the rule that inbound HTTP adapters MUST depend on the Protocol, not on the concrete use case class.
- `architecture-conformance`: Import-linter contracts that enforce hexagonal boundaries (per-feature layering, cross-feature isolation, platform isolation, tests scope).
- `api-runtime`: HTTP adapter conventions for FastAPI in this template — return types vs `response_model`, router-level `dependencies` for write auth, tagging, Problem+JSON, request id middleware, FastAPI CLI entrypoint, lifespan/composition wiring.

### Modified Capabilities
<!-- None: openspec/specs/ is empty; this is the first set of canonical specs for the template. -->

## Impact

- **Filesystem**: Every file under `src/` moves. `tests/` does not exist yet so no test impact here (tests are introduced in a separate change).
- **Imports**: Every internal import path changes (e.g., `src.application.use_cases.board.create_board` → `src.features.kanban.application.use_cases.board.create_board`).
- **Configuration**: `pyproject.toml` import-linter section is rewritten; `[tool.fastapi]` block added.
- **Tooling**: `Makefile` `dev` target switches to `fastapi dev`; `Dockerfile` `CMD` switches to `fastapi run`.
- **Migrations**: `alembic/env.py` and any `target_metadata` import path is updated; migration files themselves remain untouched.
- **No runtime behavior change**: The HTTP API surface (paths, status codes, payload shapes, Problem+JSON responses) is preserved. This is a structural refactor with FastAPI-idiomatic cleanups; existing requests must continue to work identically.
- **Downstream**: Anyone who has cloned this template before will need to follow a migration note in the README.
