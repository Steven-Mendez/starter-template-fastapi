## Why

The current implementation of the Kanban application has critical architectural violations against the `clean-ddd-hexagonal` standard. Specifically, the repository adapter (`SQLModelKanbanRepository`) leaks domain orchestration by invoking business rules (`validate_card_move`, `reorder_between_columns`), and the `KanbanRepository` acts per-entity (Cards, Columns) rather than per-aggregate-root (`Board`). This refactoring resolves these anti-patterns, ensuring clean separation of concerns and robust maintainability.

## What Changes

- **Repository Structure Restructuring**: Refactor the `KanbanRepository` to strictly manage the persistence of the `Board` aggregate root instead of individual `Card` and `Column` entities.
- **Handler Orchestration Extraction**: Relocate the business validation (`validate_card_move`) and sequence modification logic from the SQLModel repository adapter into the application layer (`src/application/commands.py`).
- **Port Realignment**: Move the repository interface definition from the application layer (`src/application/ports`) to the domain layer (e.g., `src/domain/kanban/repository.py`) to align with strict hexagonal specifications for Driven Ports.
- **BREAKING**: Function signatures in the `KanbanRepository` interface will change. Code calling these repositories (mostly application commands) will be updated.

## Capabilities

### New Capabilities
- `repository-aggregate-compliance`: Defining strict interfaces for aggregate-level operations and enforcing them internally across persistence layers.

### Modified Capabilities
- `hexagonal-layer-boundaries`: Refining how application layer interacts with Domain driven ports.

## Impact

- **Code Affected**:
  - `src/application/commands.py` (Command handers will take over logic coordination).
  - `src/infrastructure/persistence/sqlmodel_repository.py` (Will become purely generic I/O).
  - `src/application/ports/repository.py` (Moved and modified).
- **Architecture**: Enforces the domain pattern explicitly.
- **Tests**: Unit tests covering mock repositories and command handlers will require updates.
