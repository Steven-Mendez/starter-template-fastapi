# Hexagonal Dependency Rules

This project follows a strict inward dependency flow:

- `src/domain/*` has no dependencies on `src/application`, `src/api`, or `src/infrastructure`.
- `src/application/*` depends on domain models and shared result/errors only.
- `src/api/*` is an inbound adapter that maps HTTP DTOs to application inputs and maps application/domain outputs back to HTTP response DTOs.
- `src/infrastructure/*` is a driven adapter that implements domain/application ports and persists aggregate state.
- Composition/root wiring is explicit: adapter selection and Unit of Work factory selection live in `src/infrastructure/config/di/composition.py` and are consumed by `src/api/dependencies.py`.

## Lightweight CQRS

Application orchestration is split into:

- `src/application/commands/*` for mutable use cases.
- `src/application/queries/*` for read-only use cases.

The API router composes both handlers but keeps the public HTTP contract stable.
**Strict Adapter Delegation:** API routes must delegate exclusively to command or query handlers. Read endpoints (`GET`) use `KanbanQueryHandlers`, while write endpoints (`POST`, `PATCH`, `DELETE`) use `KanbanCommandHandlers`. API routes never depend directly on infrastructure/repository adapters.
**Strict FastAPI Dependency Contract:** route dependencies are expressed through reusable `Annotated` aliases defined in `src/api/dependencies.py`.

## Current Package Map

- `src/domain/kanban/models/*`: entities/value objects used across domain and application.
- `src/domain/kanban/specifications/*`: canonical movement/business rules.
- `src/domain/kanban/repository/*`: command/query repository port protocols.
- `src/application/shared/unit_of_work.py`: transaction boundary protocol.
- `src/api/mappers/kanban/*`: transport boundary mapping layer.
- `src/api/schemas/*`: transport-only request/response contracts.
- `src/infrastructure/persistence/*`: adapter implementations.

## Enforcement

- `tests/unit/test_hexagonal_boundaries.py` enforces direct and transitive dependency boundaries.
- Architecture diagnostics include violated rule, source module, and disallowed target/path for faster remediation.
