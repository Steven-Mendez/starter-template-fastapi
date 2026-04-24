## MODIFIED Requirements

### Requirement: Repositories SHALL manage Data implicitly through the Aggregate Root
The system SHALL enforce the pattern of "One repository per AGGREGATE", treating the Kanban `Board` as the Aggregate Root for persistence and mutation workflows involving child entities (Cards, Columns), and SHALL keep production adapter public APIs aligned with aggregate repository ports.

#### Scenario: Sub-entities are not persisted individually
- **WHEN** updating a card's position or creating a new column
- **THEN** the database adapter interface SHALL receive pre-calculated, verified aggregate state values and SHALL NOT orchestrate child-entity business operations internally

#### Scenario: Repository contract surface stays aggregate-oriented
- **WHEN** driven repository ports are defined for Kanban persistence
- **THEN** public contract methods SHALL focus on aggregate load/save/delete operations and SHALL NOT expose standalone child-entity CRUD orchestration methods

#### Scenario: Adapter public surface matches driven port
- **WHEN** a persistence adapter implements the Kanban repository port
- **THEN** public production methods on the adapter SHALL be declared by the driven port contract, and non-port child-entity helper methods SHALL NOT be exposed as production API

#### Scenario: Test support follows aggregate boundaries
- **WHEN** test builders or repository contract tests prepare Kanban state
- **THEN** they SHALL use aggregate-oriented operations (repository port or command handlers) and SHALL NOT depend on adapter-only child-entity helper methods
