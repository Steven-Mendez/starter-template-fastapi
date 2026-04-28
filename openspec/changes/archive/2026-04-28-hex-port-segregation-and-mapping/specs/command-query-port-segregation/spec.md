## ADDED Requirements

### Requirement: Command Port Cohesion
Command-side ports MUST expose only mutation and command-consistency behaviors required to execute business commands.

#### Scenario: Command port excludes projection queries
- **WHEN** a command repository port is defined or modified
- **THEN** it does not include list, summary, or projection-oriented read methods

#### Scenario: Command flow uses dedicated lookup abstraction
- **WHEN** a command handler requires lightweight read context for preconditions
- **THEN** it depends on a dedicated lookup port or aggregate load operation rather than a query projection port

### Requirement: Query Port Cohesion
Query-side ports MUST expose read-model retrieval behavior and MUST NOT include mutation methods.

#### Scenario: Query port serves projection contract only
- **WHEN** a query use case requests board summary data
- **THEN** the query port returns read-model objects designed for query scenarios without mutating state
