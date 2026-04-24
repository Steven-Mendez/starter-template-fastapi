# Hexagonal Dependency Rules

This project follows a strict inward dependency flow:

- `src/domain/*` has no dependencies on `src/application`, `src/api`, or `src/infrastructure`.
- `src/application/*` owns adapter-facing contracts (results/errors/read models) and can depend on domain ports/models.
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
- `src/domain/kanban/repository/*`: command/query repository port protocols.
- `src/application/commands/port.py` and `src/application/queries/port.py`: command/query driver ports.
- `src/application/contracts/*`: application-owned contracts consumed by inbound adapters.
- `src/application/shared/unit_of_work.py`: transaction boundary protocol.
- `src/api/mappers/kanban/*`: transport boundary mapping layer.
- `src/api/schemas/*`: transport-only request/response contracts (including wire enums such as `CardPrioritySchema`).
- `src/infrastructure/persistence/*`: adapter implementations with public methods constrained to driven repository ports.

## Enforcement

- `tests/unit/test_hexagonal_boundaries.py` enforces direct/transitive dependency boundaries, API schema transport ownership, inbound port usage, and adapter public-surface parity with repository ports.
- Architecture diagnostics include violated rule, source module, and disallowed target/path for faster remediation.
