# hexagonal-layer-boundaries Specification

## Purpose

Define inward-only dependencies and transport-only inbound adapters for the Kanban bounded context.
## Requirements
### Requirement: Layered dependency direction SHALL point inward
The system SHALL separate Kanban code into domain, application, and infrastructure concerns such that dependency imports only point inward toward domain and application abstractions, including transitive imports through shared helper modules.

#### Scenario: Domain layer remains framework-independent
- **WHEN** domain modules are analyzed for imports
- **THEN** they SHALL NOT import FastAPI, SQLModel/SQLAlchemy session handling, or application settings modules

#### Scenario: Infrastructure depends on ports, not the reverse
- **WHEN** persistence adapters implement repository behavior
- **THEN** infrastructure modules SHALL depend on application/domain port contracts and SHALL NOT be imported by those contracts

#### Scenario: API transitive import chain remains infrastructure-free
- **WHEN** an API adapter imports an intermediate helper/dependency module
- **THEN** the transitive import chain from that API module SHALL NOT depend on infrastructure modules

### Requirement: Inbound adapters SHALL be transport-only
The system SHALL ensure API routes depend on focused handler/settings dependencies and SHALL forbid direct coupling to container-provider internals.

#### Scenario: Route does not depend on container provider callable
- **WHEN** route dependency metadata is inspected
- **THEN** no route SHALL depend directly on `get_app_container` (or equivalent container provider) as a route-level dependency

### Requirement: Infrastructure Adapters SHALL NOT contain domain orchestration logic
The system SHALL ensure that adapters implementing driven ports (for example database repositories) remain pure I/O components that persist pre-validated state and SHALL NOT execute business orchestration decisions.

#### Scenario: Infrastructure orchestration is avoided
- **WHEN** a state change is persisted to a database
- **THEN** the adapter SHALL purely persist the values and SHALL NOT invoke domain services like `validate_card_move`

#### Scenario: Sequence decisions are application/domain owned
- **WHEN** card movement state is saved
- **THEN** adapters SHALL persist pre-computed target columns and positions and SHALL NOT calculate movement decisions internally

### Requirement: Driven Repository Ports SHALL reside in the Domain layer

The system SHALL define aggregate persistence interfaces within the Domain layer alongside the Aggregate Root, rather than in the Application layer.

#### Scenario: Driven Ports are Domain-defined

- **WHEN** resolving driven ports for repositories
- **THEN** the interface definition SHALL be found in the `src/domain/` directory alongside the affected aggregate
