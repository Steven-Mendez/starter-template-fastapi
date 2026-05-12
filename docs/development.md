# Developer Guide

This guide explains how to work on the project locally.

## Prerequisites

- Python 3.14.
- `uv`.
- Docker for local PostgreSQL and integration tests.

## Setup

```bash
cp .env.example .env
uv sync
docker compose up -d db
uv run alembic upgrade head
```

Run the development server:

```bash
make dev
```

The Makefile sets `PORT ?= 8000`. Override it when needed:

```bash
make dev PORT=8080
```

## Local Workflow

1. Create or update code under `src/`.
2. Add or update tests next to the affected feature or platform package.
3. Run focused tests while developing.
4. Run `make quality` before broad testing.
5. Run `make test` before handing off changes.
6. Run `make test-integration` when persistence behavior changes.

Useful commands:

| Command | Purpose |
| --- | --- |
| `make format` | Format with Ruff. |
| `make lint` | Lint with Ruff. |
| `make lint-fix` | Apply Ruff fixes. |
| `make lint-arch` | Check import-linter architecture contracts. |
| `make typecheck` | Run mypy. |
| `make quality` | Run lint, architecture lint, and type checks. |
| `make test` | Run unit and e2e tests excluding integration. |
| `make test-feature FEATURE=kanban` | Run tests for one feature. |
| `make test-integration` | Run Docker-backed persistence tests. |
| `make report` | Generate HTML test and coverage reports. |

## Coding Conventions

- Keep domain code pure. Do not import FastAPI, Pydantic, SQLModel,
  SQLAlchemy, Alembic, or platform API code into the domain layer.
- Keep application use cases framework-free. Use commands, queries, contracts,
  ports, and `Result[T, ApplicationError]`.
- Keep HTTP schemas and HTTP errors inside inbound adapters.
- Keep SQLModel tables, SQL queries, and unit of work code inside outbound
  adapters.
- Use `@dataclass(slots=True)` for use cases and mutable domain entities when it
  matches the existing pattern.
- Use `@dataclass(frozen=True, slots=True)` for immutable commands, queries, and
  read contracts when it matches the existing pattern.
- Declare FastAPI dependencies with `Annotated` type aliases where the existing
  code does so.
- Prefer explicit return types on path operations and use cases.

## Testing Strategy

The test suite is organized by scope.

| Scope | Location | Marker | Purpose |
| --- | --- | --- | --- |
| Unit | `src/platform/tests/` and `src/features/kanban/tests/unit/` | `unit` | Test pure domain logic, use cases, settings, middleware, and platform errors. |
| End-to-end | `src/features/kanban/tests/e2e/` | `e2e` | Test HTTP flows through FastAPI with in-memory fakes. |
| Contract | `src/features/kanban/tests/contracts/` | called by unit and integration tests | Reuse repository behavior tests against fake and SQLModel adapters. |
| Integration | `src/features/kanban/tests/integration/` | `integration` | Test SQLModel persistence against PostgreSQL through testcontainers. |

Run fast tests:

```bash
make test
```

Run Docker-backed tests:

```bash
make test-integration
```

Skip testcontainers explicitly:

```bash
KANBAN_SKIP_TESTCONTAINERS=1 make test-integration
```

## Debugging Tips

- Check `X-Request-ID` in responses and logs to correlate a request with an
  access log entry.
- Use `/health/ready` to confirm whether readiness dependencies can be reached.
- If a write route returns `401`, check `APP_WRITE_API_KEY` and the `X-API-Key`
  request header.
- If a path request returns `422`, confirm the path ID is a valid UUID string.
- If migrations target the wrong database, inspect `APP_POSTGRESQL_DSN`; Alembic
  reads it before falling back to `AppSettings` defaults.
- If an import-linter contract fails, inspect the relevant contract in
  `pyproject.toml` and move code toward the appropriate layer.

## Where To Add Code

| Change | Add or edit files |
| --- | --- |
| New HTTP route for Kanban | `src/features/kanban/adapters/inbound/http/` plus schemas and mappers as needed. |
| New Kanban use case | `src/features/kanban/application/commands/` or `queries/`, `ports/inbound/`, and `use_cases/`. |
| New domain rule | `src/features/kanban/domain/` and domain unit tests. |
| New persistence behavior | `src/features/kanban/adapters/outbound/persistence/sqlmodel/` and repository contract or integration tests. |
| New database schema change | SQLModel models plus a new Alembic migration under `alembic/versions/`. |
| New cross-cutting platform behavior | `src/platform/` with platform tests under `src/platform/tests/`. |
| New feature | Recover the scaffold from git history or the `examples/kanban` branch and follow [Feature Template Guide](feature-template.md). |

## Adding A Migration

Update SQLModel table definitions first, then create a migration:

```bash
uv run alembic revision --autogenerate -m "describe change"
```

Review the generated migration before applying it:

```bash
uv run alembic upgrade head
```

The current Alembic environment resolves the database URL from
`APP_POSTGRESQL_DSN`, then falls back to `AppSettings().postgresql_dsn`.

## Generated Reports

Coverage and HTML test reports are generated under `reports/` by Makefile
targets. They are runtime artifacts, not committed project documentation.

Generate reports:

```bash
make report
```

Remove generated reports:

```bash
make clean-reports
```
