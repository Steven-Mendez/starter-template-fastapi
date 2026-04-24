## ADDED Requirements

### Requirement: CQRS entry points SHALL be exposed as driver ports
The system SHALL expose command and query entry contracts as application-layer driver-port protocols so inbound adapters depend on stable interfaces rather than concrete handler implementations.

#### Scenario: Command handler implements command driver port
- **WHEN** command-side application handlers are defined
- **THEN** they SHALL implement a command driver-port protocol that represents write use-case entry points

#### Scenario: Query handler implements query driver port
- **WHEN** query-side application handlers are defined
- **THEN** they SHALL implement a query driver-port protocol that represents read use-case entry points

#### Scenario: API adapters consume CQRS ports
- **WHEN** API route dependency signatures are inspected
- **THEN** adapter parameters SHALL reference command/query driver-port protocols and SHALL NOT require concrete handler classes

#### Scenario: Command port instances come from composition root
- **WHEN** API dependencies resolve command handlers
- **THEN** command-port instances SHALL be provided by composition-root factories and SHALL NOT be instantiated directly in API dependency modules
