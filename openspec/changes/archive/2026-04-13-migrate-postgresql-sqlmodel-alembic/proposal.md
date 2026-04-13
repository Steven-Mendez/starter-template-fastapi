## Why

The project currently relies on SQLite-specific persistence, which limits production-readiness and schema evolution workflows. Migrating to PostgreSQL with SQLModel and Alembic enables a robust relational backend with controlled, versioned database migrations.

## What Changes

- Add PostgreSQL as the primary relational database target for runtime and local development.
- Introduce SQLModel-based ORM models and session management integrated with FastAPI dependencies.
- Add Alembic migration tooling and baseline migration scripts for schema lifecycle management.
- Replace SQLite-focused repository wiring with SQLModel/PostgreSQL-backed repository implementations.
- Update tests to follow TDD for persistence behavior and migration compatibility.

## Capabilities

### New Capabilities
- `sqlmodel-postgresql-persistence`: Define SQLModel entities, engine/session setup, and repository persistence behavior on PostgreSQL.
- `alembic-schema-migrations`: Provide migration authoring and execution workflow for schema changes.

### Modified Capabilities
- `kanban-sqlite-storage`: Transition storage requirements from SQLite-only behavior to PostgreSQL-backed persistence while preserving functional repository contracts.

## Impact

- Affected code: settings/configuration, DI dependencies, repository persistence layer, data models, and tests.
- New dependencies: `sqlmodel`, `alembic`, and PostgreSQL driver (`psycopg`).
- Operational changes: environment variables for PostgreSQL connection and migration commands for schema setup.
