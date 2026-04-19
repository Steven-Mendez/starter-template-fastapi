## MODIFIED Requirements

### Requirement: Runtime adapter selection SHALL be centralized
The system SHALL centralize settings-driven adapter and transaction strategy selection in a composition root module, and SHALL keep this logic out of route dependencies and repository port modules.

#### Scenario: Backend and transaction strategy are selected in one place
- **WHEN** application settings specify `inmemory`, `sqlite`, or `postgresql` backend
- **THEN** composition root wiring SHALL instantiate the matching repository adapter and the matching Unit of Work factory

#### Scenario: Request dependencies do not perform runtime adapter selection
- **WHEN** route dependencies resolve command/query handlers for a request
- **THEN** they SHALL consume pre-wired container contracts and SHALL NOT construct repository or Unit of Work implementations lazily

### Requirement: Lifecycle management SHALL be owned by composition root
The system SHALL own startup/shutdown lifecycle hooks for stateful adapters and container state in composition root wiring.

#### Scenario: Repository resources are closed on shutdown
- **WHEN** the application lifecycle ends
- **THEN** composition root shutdown logic SHALL call adapter close/disposal hooks exactly once

#### Scenario: Missing container state fails fast
- **WHEN** a request dependency executes without initialized container state
- **THEN** it SHALL raise an explicit lifecycle/configuration error and SHALL NOT initialize a new container implicitly

## ADDED Requirements

### Requirement: Unit of Work factory SHALL be explicit in composition contracts
The system SHALL expose Unit of Work creation through an explicit composition-root contract instead of repository implementation introspection.

#### Scenario: Command handlers are created from an explicit Unit of Work factory
- **WHEN** command handler dependencies are resolved for a request
- **THEN** handlers SHALL be instantiated using a Unit of Work produced by a composition-root-provided factory

#### Scenario: Private repository attributes are not used for strategy selection
- **WHEN** selecting a Unit of Work implementation
- **THEN** the system SHALL NOT inspect repository private attributes (for example `_engine`) to infer transaction strategy
