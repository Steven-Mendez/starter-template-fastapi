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
The system SHALL ensure HTTP route handlers act as primary adapters that translate requests/responses and delegate orchestration to command/query handlers in the application layer.

#### Scenario: Route handler orchestration is delegated
- **WHEN** a route performs a Kanban command or query
- **THEN** the route SHALL call an application handler dependency and SHALL NOT call persistence adapters directly

#### Scenario: Handler dependencies stay adapter-edge and typed
- **WHEN** FastAPI dependencies are declared by route handlers
- **THEN** the adapter SHALL depend on typed command/query handler contracts and SHALL NOT depend on infrastructure adapter implementations

### Requirement: Infrastructure Adapters SHALL NOT contain domain orchestration logic

The system SHALL ensure that adapters implementing driven ports (e.g. database repositories) function purely as I/O mechanisms without invoking domain validation or calculating sequence logic.

#### Scenario: Infrastructure orchestration is avoided

- **WHEN** a state change is persisted to a database
- **THEN** the adapter SHALL purely persist the values and SHALL NOT invoke domain services like `validate_card_move`

### Requirement: Driven Repository Ports SHALL reside in the Domain layer

The system SHALL define aggregate persistence interfaces within the Domain layer alongside the Aggregate Root, rather than in the Application layer.

#### Scenario: Driven Ports are Domain-defined

- **WHEN** resolving driven ports for repositories
- **THEN** the interface definition SHALL be found in the `src/domain/` directory alongside the affected aggregate
