## MODIFIED Requirements

### Requirement: Repositories SHALL manage Data implicitly through the Aggregate Root
The system SHALL enforce the pattern of "One repository per AGGREGATE", treating the Kanban `Board` as the Aggregate Root for persistence and mutation workflows involving child entities (Cards, Columns).

#### Scenario: Sub-entities are not persisted individually
- **WHEN** updating a card's position or creating a new column
- **THEN** the database adapter interface SHALL receive pre-calculated, verified aggregate state values and SHALL NOT orchestrate child-entity business operations internally

#### Scenario: Repository contract surface stays aggregate-oriented
- **WHEN** driven repository ports are defined for Kanban persistence
- **THEN** public contract methods SHALL focus on aggregate load/save/delete operations and SHALL NOT expose standalone child-entity CRUD orchestration methods

#### Scenario: Adapter methods honor aggregate boundary
- **WHEN** a persistence adapter implements the Kanban repository port
- **THEN** it SHALL implement aggregate-oriented operations required by the port and SHALL NOT introduce alternative child-entity orchestration entry points as part of that port contract
