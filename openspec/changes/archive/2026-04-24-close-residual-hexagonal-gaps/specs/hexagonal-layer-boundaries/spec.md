## MODIFIED Requirements

### Requirement: Inbound adapters SHALL be transport-only
The system SHALL ensure HTTP route handlers act as primary adapters that map transport payloads and transport responses to application contracts, delegate orchestration to command/query handlers through driver-port interfaces, and SHALL NOT import domain entities, domain errors, or domain result abstractions directly.

#### Scenario: Route handler orchestration is delegated
- **WHEN** a route performs a Kanban command or query
- **THEN** the route SHALL call an application driver-port dependency and SHALL NOT call persistence adapters directly

#### Scenario: Handler dependencies use driver ports, not concrete classes
- **WHEN** FastAPI dependencies are declared by route handlers
- **THEN** the adapter SHALL depend on typed command/query driver-port protocols and SHALL NOT require concrete handler class annotations

#### Scenario: Routes avoid direct container injection
- **WHEN** API route signatures are analyzed
- **THEN** routes SHALL consume dedicated handler/settings dependencies and SHALL NOT inject the app container object directly

#### Scenario: API dependency layer has no repository bypass provider
- **WHEN** API dependency modules are inspected
- **THEN** they SHALL expose command/query handler dependencies for routes and SHALL NOT expose repository injection helpers that allow bypassing handlers

#### Scenario: API adapter contract leakage is rejected
- **WHEN** an API adapter module imports a domain model, domain error, or domain result module
- **THEN** architecture checks SHALL fail with an explicit boundary violation
