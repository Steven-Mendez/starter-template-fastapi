# kanban-repository Specification

## Purpose

Define a stable outbound repository port for Kanban aggregates that preserves domain invariants, explicit error semantics, and command/query separation without leaking transport or framework concerns.

## Requirements

### Requirement: Repository exposes board and column operations with explicit failures

The system SHALL provide a `KanbanRepository` protocol as an outbound port. Operations that may fail SHALL return `Result[T, KanbanError]` using `Ok` for success and `Err` for failure. `KanbanError` SHALL be a `StrEnum` of stable reason codes; each member SHALL expose a `detail` string suitable for HTTP error bodies. The contract SHALL be satisfied by all supported repository backends. Repositories that hold external resources MAY expose close/disposal hooks and callers SHALL release those resources in lifecycle teardown. The outbound port definition SHALL remain independent of framework request objects and runtime settings-based adapter selection.

#### Scenario: Missing board returns Err on read

- **WHEN** `get_board` is called with an id that does not exist
- **THEN** the result SHALL be `Err` with `code` indicating not found

#### Scenario: Deleting a missing board returns Err

- **WHEN** `delete_board` is called for an unknown id
- **THEN** the result SHALL be `Err` (not a silent `False`)

### Requirement: Card updates distinguish invalid cross-board moves

The system SHALL represent an attempt to move a card to a column on a different board as a failure distinct from a simple missing id where useful for tests. The move rule SHALL be evaluated through domain specification objects.

#### Scenario: Cross-board column target yields invalid-move error

- **WHEN** card movement targets a column that belongs to another board than the card's current board
- **THEN** the result SHALL be `Err` with an error code for invalid move

### Requirement: Repository contracts SHALL support CQRS-oriented split

The system SHALL allow application-level separation between command-side and query-side contracts while preserving consistent domain invariants and error semantics.

#### Scenario: Query contract does not expose write methods

- **WHEN** a query-side application handler is type-checked
- **THEN** its repository dependency SHALL include read operations only

#### Scenario: Command contract can mutate state

- **WHEN** a command-side application handler is type-checked
- **THEN** its repository dependency SHALL include write operations required by the command

### Requirement: Repositories SHALL persist through Aggregates

The system SHALL limit repository interfaces to persist entire aggregates (for example `Board`), effectively discouraging direct CRUD manipulation of sub-entities outside of the aggregate boundary concept.

#### Scenario: Board operates as the persistence aggregate boundary

- **WHEN** the repository is tasked with persisting a modified board state
- **THEN** the application SHALL NOT issue raw granular table-level updates bypassing aggregate-root logic
