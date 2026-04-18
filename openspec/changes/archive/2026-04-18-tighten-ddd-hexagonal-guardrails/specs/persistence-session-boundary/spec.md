## ADDED Requirements

### Requirement: Repository adapters SHALL own explicit session boundaries
The system SHALL ensure persistence adapters use explicit session scopes for each repository operation, with commit/refresh behavior defined in adapter code and no session handling in domain modules.

#### Scenario: SQLModel repository operation executes in scoped session
- **WHEN** a SQLModel-backed repository method performs a read or write
- **THEN** it SHALL execute inside a bounded `Session` scope and close scope on completion

#### Scenario: Domain remains persistence-session agnostic
- **WHEN** domain modules are analyzed for imports and symbols
- **THEN** they SHALL NOT reference SQLModel `Session`, SQLAlchemy transaction APIs, or engine configuration

### Requirement: Adapter lifecycle SHALL align with application composition
The system SHALL initialize and dispose long-lived persistence resources through composition/lifespan wiring, while keeping per-operation sessions local to adapters.

#### Scenario: Application shutdown disposes repository resources
- **WHEN** application lifespan exits
- **THEN** repository resources that support explicit close/dispose SHALL be invoked exactly once by composition wiring
