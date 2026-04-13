## Context

The current persistence implementation centers on SQLite and repository abstractions tailored to local-file storage. This limits production deployment options and does not provide a robust schema migration workflow. The target architecture introduces PostgreSQL for runtime persistence, SQLModel for ORM/data mapping, and Alembic for versioned schema migrations while preserving existing domain and API behavior.

## Goals / Non-Goals

**Goals:**
- Enable PostgreSQL-backed persistence for kanban entities with SQLModel.
- Introduce deterministic schema migration workflows using Alembic.
- Preserve repository contract semantics and error/result behavior.
- Implement the migration using TDD, starting from failing tests.

**Non-Goals:**
- Rewriting domain models and business rules.
- Introducing advanced PostgreSQL features (partitioning, materialized views, etc.).
- Building a zero-downtime multi-step live migration from existing SQLite data files.

## Decisions

- Use SQLModel table models for persistence mapping while keeping domain entities unchanged.
  - Alternative considered: SQLAlchemy declarative models directly. Rejected to keep a simpler, typed model layer aligned with FastAPI/Pydantic usage.
- Use a PostgreSQL DSN from settings as the primary database configuration.
  - Alternative considered: dual write/read to SQLite and PostgreSQL. Rejected due to unnecessary complexity for the current migration scope.
- Use Alembic with SQLModel metadata as migration source of truth.
  - Alternative considered: `SQLModel.metadata.create_all()` at startup only. Rejected because it is not suitable for controlled schema evolution across environments.
- Keep repository-level selection via dependency wiring so tests can continue to substitute in-memory backends.
  - Alternative considered: hard-binding PostgreSQL repository globally. Rejected to preserve testability and existing architecture boundaries.

## Risks / Trade-offs

- [Risk] SQL dialect differences may break assumptions currently validated only on SQLite. -> Mitigation: add integration tests covering key repository operations against PostgreSQL.
- [Risk] Migration scripts and SQLModel models can drift. -> Mitigation: enforce Alembic autogenerate workflow and test migration upgrade path in CI/local runs.
- [Risk] Local developer setup becomes heavier due to PostgreSQL requirement. -> Mitigation: provide clear environment configuration and default test strategy with isolated database URLs.

## Migration Plan

1. Add failing tests asserting PostgreSQL repository wiring and SQLModel persistence behavior.
2. Introduce SQLModel models, engine/session setup, and repository implementation updates.
3. Add Alembic configuration and create baseline migration for current schema.
4. Make tests pass and validate upgrade path (`alembic upgrade head`).
5. Document required environment variables and migration commands.

Rollback strategy:
- Revert deployment to previous revision and run down-migration if needed.
- Keep migration history versioned to allow controlled rollback.

## Open Questions

- Should the project maintain a SQLite fallback mode for local-only usage after migration?
- Should migration checks be added as a dedicated CI gate in this iteration or follow-up change?
