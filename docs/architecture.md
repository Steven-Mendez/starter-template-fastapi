# Hexagonal Dependency Rules

This project follows a strict inward dependency flow:

- `src/domain/*` has no dependencies on `src/application`, `src/api`, or `src/infrastructure`.
- `src/application/*` depends on domain models and shared result/errors only.
- `src/api/*` is an inbound adapter that maps HTTP DTOs to application inputs and maps application/domain outputs back to HTTP response DTOs.
- `src/infrastructure/*` is a driven adapter that implements application ports and persists domain/application models.

## Lightweight CQRS

Application orchestration is split into:

- `src/application/commands.py` for mutable use cases.
- `src/application/queries.py` for read-only use cases.

The API router composes both handlers but keeps the public HTTP contract stable.
**Strict Adapter Delegation:** API routes must delegate exclusively to command or query handlers. Read endpoints (GET) must use `KanbanQueryHandlers`, while write endpoints (POST, PATCH, DELETE) must use `KanbanCommandHandlers`. API routes must never depend directly on infrastructure/repository adapters.

## Current Package Map

- `src/domain/kanban/models.py`: entities/value objects used across domain and application.
- `src/domain/kanban/specifications/*`: canonical movement/business rules.
- `src/application/ports/repository.py`: command/query port protocols.
- `src/api/mappers/kanban.py`: boundary mapping layer.
- `src/infrastructure/persistence/*`: adapter implementations.
