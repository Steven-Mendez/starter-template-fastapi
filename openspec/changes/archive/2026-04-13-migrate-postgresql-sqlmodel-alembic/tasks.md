## 1. Test-first migration scaffolding

- [x] 1.1 Add failing tests for SQLModel/PostgreSQL repository selection and persistence semantics
- [x] 1.2 Add failing test coverage for migration configuration expectations (Alembic config and metadata binding)

## 2. SQLModel PostgreSQL persistence implementation

- [x] 2.1 Add SQLModel engine/session configuration driven by settings
- [x] 2.2 Implement/update repository persistence wiring to use SQLModel PostgreSQL backend
- [x] 2.3 Ensure repository behavior preserves domain result/error semantics

## 3. Alembic integration

- [x] 3.1 Add Alembic project configuration and env wiring to SQLModel metadata
- [x] 3.2 Create baseline migration for kanban schema tables and relationships

## 4. Validation and documentation

- [x] 4.1 Make tests pass and run migration upgrade verification locally
- [x] 4.2 Update README/config docs for PostgreSQL and Alembic workflows
