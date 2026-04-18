## MODIFIED Requirements

### Requirement: Repository exposes board and column operations with explicit failures

The system SHALL provide a `KanbanRepository` protocol as an outbound port. Operations that may fail SHALL return `Result[T, KanbanError]` using `Ok` for success and `Err` for failure. `KanbanError` SHALL be a `StrEnum` of stable reason codes; each member SHALL expose a `detail` string suitable for HTTP error bodies (see `kanban/errors.py`). The contract SHALL be satisfied by all supported repository backends. Repositories that hold external resources MAY expose close/disposal hooks and callers SHALL release those resources in lifecycle teardown. The outbound port definition SHALL remain independent of framework request objects and runtime settings-based adapter selection.

#### Scenario: Missing board returns Err on read

- **WHEN** `get_board` is called with an id that does not exist
- **THEN** the result SHALL be `Err` with `code` indicating not found

#### Scenario: Deleting a missing board returns Err

- **WHEN** `delete_board` is called for an unknown id
- **THEN** the result SHALL be `Err` (not a silent `False`)
