## ADDED Requirements

### Requirement: Kanban store exposes explicit Result outcomes

The Kanban domain store SHALL represent the outcome of operations that can fail using a `Result` type with `Ok` and `Err` variants and a `KanbanError` enumeration, instead of using `None` or bare booleans to indicate failure.

#### Scenario: Missing board returns structured error

- **WHEN** a client of the store requests a board by id that does not exist
- **THEN** the store SHALL return `Err` with an error value that identifies the missing board (for example a not-found board variant)

#### Scenario: Successful mutation returns Ok

- **WHEN** a store operation completes successfully
- **THEN** the store SHALL return `Ok` with the appropriate value (including `Ok(None)` for void successes such as delete)

### Requirement: Domain errors are enumerable

The system SHALL define `KanbanError` such that failure reasons relevant to Kanban operations (including resource not found and invalid card move) are represented as distinct enum values.

#### Scenario: Invalid card move is distinguishable

- **WHEN** a card move violates board or column rules (for example moving to a column on another board)
- **THEN** the store SHALL fail with an error distinct from a simple missing identifier where applicable
