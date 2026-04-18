## MODIFIED Requirements

### Requirement: Repository persistence SHALL run on PostgreSQL through SQLModel
The system SHALL persist kanban boards, columns, and cards in PostgreSQL using SQLModel table mappings and sessions, while keeping SQLModel concerns contained in infrastructure adapters.

#### Scenario: Persist and read board aggregate
- **WHEN** a board with columns and cards is created through the repository
- **THEN** a subsequent repository query SHALL return the same board state from PostgreSQL

#### Scenario: SQLModel symbols remain in infrastructure layer
- **WHEN** imports are analyzed for domain and application modules
- **THEN** SQLModel/SQLAlchemy engine or session symbols SHALL only appear in infrastructure persistence adapters

### Requirement: Persistence wiring SHALL be configurable via database URL
The system SHALL build SQLModel engine/session configuration from application settings so environments can provide PostgreSQL connection details, and adapter creation SHALL be owned by composition-root wiring rather than repository port modules.

#### Scenario: PostgreSQL URL provided in settings
- **WHEN** the application starts with a PostgreSQL database URL configured
- **THEN** repository dependencies SHALL use SQLModel-backed PostgreSQL persistence

#### Scenario: Composition root selects PostgreSQL adapter
- **WHEN** backend configuration resolves to PostgreSQL
- **THEN** composition root wiring SHALL instantiate the SQLModel PostgreSQL adapter used by application ports

#### Scenario: Session scope is operation-bound
- **WHEN** a repository method completes a PostgreSQL-backed operation
- **THEN** session scope SHALL end for that operation and transaction boundaries SHALL be explicit in adapter code
