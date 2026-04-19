## ADDED Requirements

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
