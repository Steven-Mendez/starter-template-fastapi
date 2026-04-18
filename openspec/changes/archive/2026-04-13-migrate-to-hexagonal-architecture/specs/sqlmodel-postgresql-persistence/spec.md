## MODIFIED Requirements

### Requirement: Persistence wiring SHALL be configurable via database URL
The system SHALL build SQLModel engine/session configuration from application settings so environments can provide PostgreSQL connection details, and adapter creation SHALL be owned by composition-root wiring rather than repository port modules.

#### Scenario: PostgreSQL URL provided in settings
- **WHEN** the application starts with a PostgreSQL database URL configured
- **THEN** repository dependencies SHALL use SQLModel-backed PostgreSQL persistence

#### Scenario: Composition root selects PostgreSQL adapter
- **WHEN** backend configuration resolves to PostgreSQL
- **THEN** composition root wiring SHALL instantiate the SQLModel PostgreSQL adapter used by application ports
