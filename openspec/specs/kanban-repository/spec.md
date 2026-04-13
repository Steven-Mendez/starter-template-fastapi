# kanban-repository Specification

## Purpose

Define how Kanban data is accessed through a repository abstraction with explicit success and failure outcomes, without changing the HTTP API behavior of the `kanban-board` capability.

## Requirements

### Requirement: Repository exposes board and column operations with explicit failures

The system SHALL provide a `KanbanRepository` protocol. Operations that may fail SHALL return `Result[T, KanbanError]` using `Ok` for success and `Err` for failure. `KanbanError` SHALL be a `StrEnum` of stable reason codes; each member SHALL expose a `detail` string suitable for HTTP error bodies (see `kanban/errors.py`). The contract SHALL be satisfied by all supported repository backends. Repositories that hold external resources MAY expose close/disposal hooks and callers SHALL release those resources in lifecycle teardown.

#### Scenario: Missing board returns Err on read

- **WHEN** `get_board` is called with an id that does not exist
- **THEN** the result SHALL be `Err` with `code` indicating not found

#### Scenario: Deleting a missing board returns Err

- **WHEN** `delete_board` is called for an unknown id
- **THEN** the result SHALL be `Err` (not a silent `False`)

### Requirement: Card updates distinguish invalid cross-board moves

The system SHALL represent an attempt to move a card to a column on a different board as a failure distinct from a simple missing id where useful for tests. The move rule SHALL be evaluated through domain specification objects.

#### Scenario: Cross-board column target yields invalid-move error

- **WHEN** `update_card` is asked to set `column_id` to a column that exists but belongs to another board than the card's current column
- **THEN** the result SHALL be `Err` with an error code for invalid move

### Requirement: Backward-compatible entry points remain available

The system SHALL keep module-level accessors (for example `get_store`) so existing tests and dependency injection continue to work, delegating to the configured repository implementation.

#### Scenario: FastAPI dependency resolves a repository

- **WHEN** routes request the Kanban dependency
- **THEN** they SHALL receive an object satisfying `KanbanRepository`
- **THEN** backend selection SHALL follow application configuration
