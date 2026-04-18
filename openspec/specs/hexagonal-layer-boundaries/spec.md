# hexagonal-layer-boundaries Specification

## Purpose

Define inward-only dependencies and transport-only inbound adapters for the Kanban bounded context.

## Requirements

### Requirement: Layered dependency direction SHALL point inward

The system SHALL separate Kanban code into domain, application, and infrastructure concerns such that dependency imports only point inward toward domain and application abstractions.

#### Scenario: Domain layer remains framework-independent

- **WHEN** domain modules are analyzed for imports
- **THEN** they SHALL NOT import FastAPI, SQLModel/SQLAlchemy session handling, or application settings modules

#### Scenario: Infrastructure depends on ports, not the reverse

- **WHEN** persistence adapters implement repository behavior
- **THEN** infrastructure modules SHALL depend on application/domain port contracts and SHALL NOT be imported by those contracts

### Requirement: Inbound adapters SHALL be transport-only

The system SHALL ensure HTTP route handlers act as primary adapters that translate requests/responses and delegate orchestration to application use cases.

#### Scenario: Route handler orchestration is delegated

- **WHEN** a route performs a Kanban command or query
- **THEN** the route SHALL call an application use-case interface and SHALL NOT call persistence adapters directly
