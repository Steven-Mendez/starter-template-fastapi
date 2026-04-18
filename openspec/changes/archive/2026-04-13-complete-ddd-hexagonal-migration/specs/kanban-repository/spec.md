## MODIFIED Requirements

### Requirement: Repository exposes board and column operations with explicit failures

The system SHALL provide a `KanbanRepository` protocol. Operations that may fail SHALL return `Result[T, KanbanError]` using `Ok` for success and `Err` for failure. `KanbanError` SHALL be a `StrEnum` of stable reason codes; each member SHALL expose a `detail` string suitable for error translation at adapter boundaries. The contract SHALL be satisfied by all supported repository backends. Repositories that hold external resources MAY expose close/disposal hooks and callers SHALL release those resources in lifecycle teardown. Repository contracts SHALL use internal domain/application types and SHALL NOT depend on HTTP transport schema modules.

#### Scenario: Missing board returns Err on read

- **WHEN** `get_board` is called with an id that does not exist
- **THEN** the result SHALL be `Err` with `code` indicating not found

#### Scenario: Deleting a missing board returns Err

- **WHEN** `delete_board` is called for an unknown id
- **THEN** the result SHALL be `Err` (not a silent `False`)

### Requirement: Repository contracts SHALL support CQRS-oriented split

The system SHALL allow application-level separation between command-side and query-side contracts while preserving consistent domain invariants and error semantics.

#### Scenario: Query contract does not expose write methods

- **WHEN** a query-side application handler is type-checked
- **THEN** its repository dependency SHALL include read operations only

#### Scenario: Command contract can mutate state

- **WHEN** a command-side application handler is type-checked
- **THEN** its repository dependency SHALL include write operations required by the command

## REMOVED Requirements

### Requirement: Backward-compatible entry points remain available
**Reason**: The migration is now strict-architecture and no longer supports transitional compatibility shims.
**Migration**: Consumers MUST depend on the canonical ports/use-cases and infrastructure adapters in their final package locations.
