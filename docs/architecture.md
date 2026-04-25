# Hexagonal Dependency Rules

This project follows a strict inward dependency flow:

- `src/domain/*` has no dependencies on `src/application`, `src/api`, or `src/infrastructure`.
- `src/application/*` owns adapter-facing contracts (results/errors/read models and driven ports) and can depend on domain models.
- `src/api/*` is an inbound adapter that maps HTTP DTOs to application inputs and maps application outputs back to HTTP response DTOs.
- `src/api/*` depends on application driver ports (Protocols), not concrete handler classes or repositories.
- `src/infrastructure/*` is a driven adapter that implements domain/application ports and persists aggregate state.
- Composition/root wiring is explicit: adapter selection and Unit of Work factory selection live in `src/infrastructure/config/di/composition.py` and are consumed by `src/api/dependencies.py`.
- API dependency providers expose handler ports for routes and do not expose repository bypass helpers.
- API dependency providers do not instantiate concrete handlers directly; handler factories are supplied by composition-root container wiring.

## Lightweight CQRS

Application orchestration is split into:

- `src/application/commands/*` for mutable use cases.
- `src/application/queries/*` for read-only use cases.
- `src/application/commands/port.py` and `src/application/queries/port.py` define inbound driver-port contracts consumed by API dependencies.

The API router composes both handlers but keeps the public HTTP contract stable.
**Strict Adapter Delegation:** API routes must delegate exclusively to command or query handlers. Read endpoints (`GET`) use `KanbanQueryPort`, while write endpoints (`POST`, `PATCH`, `DELETE`) use `KanbanCommandPort`. API routes never depend directly on infrastructure/repository adapters.
**Strict FastAPI Dependency Contract:** route dependencies are expressed through reusable `Annotated` aliases defined in `src/api/dependencies.py`.
**No Container Injection in Routes:** route handlers consume focused dependencies (handler ports/settings) instead of injecting the app container object.

## Current Package Map

- `src/domain/kanban/models/*`: entities/value objects used across domain and application.
- `src/domain/kanban/specifications/*`: canonical movement/business rules.
- `src/application/ports/*`: driven repository port protocols owned by the application layer.
- `src/application/commands/port.py` and `src/application/queries/port.py`: command/query driver ports.
- `src/application/contracts/*`: application-owned contracts consumed by inbound adapters.
- `src/application/shared/unit_of_work.py`: transaction boundary protocol.
- `src/api/mappers/kanban/*`: transport boundary mapping layer.
- `src/api/schemas/*`: transport-only request/response contracts (including wire enums such as `CardPrioritySchema`).
- `src/infrastructure/persistence/*`: adapter implementations with public methods constrained to driven repository ports.

## Enforcement

- `tests/unit/test_hexagonal_boundaries.py` enforces direct/transitive dependency boundaries, API schema transport ownership, inbound port usage, and adapter public-surface parity with repository ports.
- Architecture diagnostics include violated rule, source module, and disallowed target/path for faster remediation.

## Architecture Linting

This repository enforces boundaries with two complementary tools:

- `import-linter` runs declarative import contracts from `pyproject.toml` and fails fast during lint/check/CI workflows.
- `tests/unit/test_hexagonal_boundaries.py` keeps structural and behavioral checks that import contracts cannot express.

Run architecture contract checks with:

```bash
make lint-arch
```

### Add a New Port Safely

1. Define the Protocol in `src/application/ports/<name>.py`.
2. Keep imports limited to domain/application modules and stdlib.
3. Run `make lint-arch` to verify no contract is violated.

### Add a New Outbound Adapter Safely

1. Add the adapter under `src/infrastructure/`.
2. Import from `src.application` ports/contracts and `src.domain` as needed.
3. Do not import from `src.api` (blocked by the infrastructure contract).
4. Run `make lint-arch` to confirm compliance.

### Add a New Inbound Adapter Safely

1. Create the adapter package (for example `src/cli/` or `src/consumer/`).
2. Extend Import Linter contract `source_modules` if the new adapter should follow API-style restrictions.
3. Depend on `src.application` contracts/ports, not `src.infrastructure`.
4. Run `make lint-arch` and update tests if adapter-specific behavioral rules are required.

### Contract Exceptions (`ignore_imports`)

- Prefer no exceptions; treat `ignore_imports` as temporary debt.
- Add a short inline comment explaining why the exception exists.
- For temporary exceptions, include a TODO with the OpenSpec change that will remove it (for example: `# TODO: remove after relocate-ports-to-application-layer`).
- Remove the exception as soon as the dependent change lands.
