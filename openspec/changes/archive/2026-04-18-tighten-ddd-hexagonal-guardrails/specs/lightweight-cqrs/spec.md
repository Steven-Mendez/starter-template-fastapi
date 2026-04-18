## MODIFIED Requirements

### Requirement: Application layer SHALL separate command and query responsibilities
The system SHALL define dedicated command handlers and query handlers (or equivalent interfaces) so write operations and read operations are not mixed in the same application contract.

#### Scenario: Board creation uses command handler
- **WHEN** an API adapter processes a board creation request
- **THEN** it SHALL invoke a command-oriented application handler

#### Scenario: Board detail retrieval uses query handler
- **WHEN** an API adapter processes a board retrieval request
- **THEN** it SHALL invoke a query-oriented application handler

#### Scenario: Read endpoint does not depend on command handler
- **WHEN** API adapter dependencies are analyzed for read-only endpoints
- **THEN** those endpoints SHALL depend on query handlers and SHALL NOT require command handlers

### Requirement: Lightweight CQRS SHALL avoid advanced infrastructure complexity
The system SHALL implement CQRS separation only at code-structure level and SHALL NOT require distributed command buses, event sourcing, or asynchronous projection pipelines.

#### Scenario: CQRS implementation remains in-process
- **WHEN** command and query handlers are wired
- **THEN** they SHALL execute in-process using the existing application composition root

#### Scenario: Handler split is validated by tests
- **WHEN** unit tests validate command/query separation
- **THEN** tests SHALL assert distinct handler contracts for mutable and read-only operations
