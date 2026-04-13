## MODIFIED Requirements

### Requirement: Repository exposes board and column operations with explicit failures
The system SHALL provide a `KanbanRepository` protocol. Operations that may fail SHALL return `Result[T, KanbanError]` using `Ok` for success and `Err` for failure. `KanbanError` SHALL be a `StrEnum` of stable reason codes; each member SHALL expose a `detail` string suitable for HTTP error bodies (see `kanban/errors.py`). The contract SHALL be satisfied by all supported repository backends.

#### Scenario: Missing board returns Err on read
- **WHEN** `get_board` is called with an id that does not exist
- **THEN** the result SHALL be `Err` with `code` indicating not found

#### Scenario: Deleting a missing board returns Err
- **WHEN** `delete_board` is called for an unknown id
- **THEN** the result SHALL be `Err` (not a silent `False`)

### Requirement: Backward-compatible entry points remain available
The system SHALL keep module-level accessors (for example `get_store`) so existing tests and dependency injection continue to work, delegating to the configured repository implementation.

#### Scenario: FastAPI dependency resolves a repository
- **WHEN** routes request the Kanban dependency
- **THEN** they SHALL receive an object satisfying `KanbanRepository`
- **THEN** backend selection SHALL follow application configuration
