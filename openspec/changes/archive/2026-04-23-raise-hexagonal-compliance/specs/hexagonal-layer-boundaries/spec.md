## MODIFIED Requirements

### Requirement: Inbound adapters SHALL be transport-only
The system SHALL ensure HTTP route handlers act as primary adapters that map transport payloads and transport responses to application contracts, delegate orchestration to command/query handlers, and SHALL NOT import domain entities, domain errors, or domain result abstractions directly.

#### Scenario: Route handler orchestration is delegated
- **WHEN** a route performs a Kanban command or query
- **THEN** the route SHALL call an application handler dependency and SHALL NOT call persistence adapters directly

#### Scenario: Handler dependencies stay adapter-edge and typed
- **WHEN** FastAPI dependencies are declared by route handlers
- **THEN** the adapter SHALL depend on typed command/query handler contracts and SHALL NOT depend on infrastructure adapter implementations

#### Scenario: API adapter contract leakage is rejected
- **WHEN** an API adapter module imports a domain model, domain error, or domain result module
- **THEN** architecture checks SHALL fail with an explicit boundary violation

### Requirement: Infrastructure Adapters SHALL NOT contain domain orchestration logic
The system SHALL ensure that adapters implementing driven ports (for example database repositories) remain pure I/O components that persist pre-validated state and SHALL NOT execute business orchestration decisions.

#### Scenario: Infrastructure orchestration is avoided
- **WHEN** a state change is persisted to a database
- **THEN** the adapter SHALL purely persist the values and SHALL NOT invoke domain services like `validate_card_move`

#### Scenario: Sequence decisions are application/domain owned
- **WHEN** card movement state is saved
- **THEN** adapters SHALL persist pre-computed target columns and positions and SHALL NOT calculate movement decisions internally
