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

## Local Email With Mailpit

`docker-compose.yml` ships a `mailpit` service that exposes an SMTP server
on `1025` and a web UI on `8025`. Point the SMTP backend at it to exercise
real SMTP wiring (auth flows, retries, large bodies) before code reaches
staging.

```bash
docker compose up -d mailpit
# in .env or shell env:
export APP_EMAIL_BACKEND=smtp
export APP_EMAIL_SMTP_HOST=mailpit       # use "localhost" when running outside compose
export APP_EMAIL_SMTP_PORT=1025
export APP_EMAIL_SMTP_USE_STARTTLS=false
export APP_EMAIL_SMTP_USE_SSL=false
```

Open <http://localhost:8025> to see captured messages from password-reset,
email-verify, or any other dispatch flow.

The compose `app` service runs with `restart: unless-stopped` and a
container-level `healthcheck` against `/health/live`, so a crashed dev app
surfaces in `docker compose ps` instead of disappearing silently.

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
| `make outbox-retry-failed` | Re-arm `outbox_messages` rows that reached `APP_OUTBOX_MAX_ATTEMPTS`. |
| `make report` | Generate HTML test and coverage reports. |

> **Outbox**: request-path use cases that both write business state and
> trigger a side effect (an email, a notification) MUST go through
> `OutboxPort.enqueue` inside the repository's `*_transaction()`
> context — never through `JobQueuePort.enqueue` directly. The token
> insert, the audit event, and the side-effect intent must commit
> atomically; only then does the relay claim the row and dispatch it
> through `JobQueuePort`. See `docs/outbox.md`.

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
| Unit | `src/app_platform/tests/` and `src/features/<feature>/tests/unit/` | `unit` | Test pure domain logic, use cases, settings, middleware, and platform errors. |
| End-to-end | `src/features/<feature>/tests/e2e/` | `e2e` | Test HTTP flows through FastAPI with in-memory fakes. |
| Contract | `src/features/<feature>/tests/contracts/` | called by unit and integration tests | Reuse repository behavior tests against fake and SQLModel adapters. |
| Integration | `src/features/<feature>/tests/integration/` | `integration` | Test SQLModel persistence against PostgreSQL through testcontainers. |

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

## Quality Gates

`make ci` enforces two coverage signals on top of `make quality` (Ruff +
Import Linter + mypy):

- **Statement (line) coverage** floor of **80%**, configured in
  `pyproject.toml [tool.coverage.report] fail_under`.
- **Branch coverage** floor of **60%**, configured as `BRANCH_COVERAGE_FLOOR`
  in the `Makefile`. The check runs after every coverage target (`cov`,
  `cov-html`, `cov-xml`) and prints both numbers explicitly. Override per-run
  with `BRANCH_COVERAGE_FLOOR=70 make cov`.

The branch-coverage floor is calibrated to what `main` achieves today, rounded
down to the nearest 5%. Bump it in a separate PR after you close concrete
coverage gaps — bundling the gate change with a ratchet makes the diff
impossible to review honestly.

## Dependency Updates

Dependency and GitHub-Actions updates are managed by [Renovate](https://docs.renovatebot.com/).
The configuration lives at `renovate.json` at the repo root. Renovate opens
grouped PRs:

| Group | Members |
| --- | --- |
| `pytest` | `pytest`, `pytest-asyncio`, `pytest-clarity`, `pytest-cov`, `pytest-html`, `pytest-randomly`, `pytest-sugar` |
| `fastapi-pydantic` | `fastapi`, `starlette`, `pydantic`, `pydantic-settings` |
| `sqlmodel-stack` | `sqlmodel`, `sqlalchemy`, `alembic` |
| `arq-redis` | `arq`, `redis`, `fakeredis` |
| `boto3` | `boto3`, `botocore`, `boto3-stubs`, `moto` |
| `dev-tooling` | `ruff`, `mypy`, `import-linter`, `pre-commit`, `pip-audit` |

`lockFileMaintenance` runs weekly (Monday before 05:00 UTC) and bumps
`uv.lock`. The Dependency Dashboard issue (auto-created when Renovate first
runs) is the canonical place to defer or trigger updates.

All `uses:` references in `.github/workflows/*.yml` are pinned to full commit
SHAs (with a `# <version>` trailing comment for readability). Renovate's
`github-actions` manager bumps the SHAs deterministically — never edit them by
hand.

> **Note.** `renovate.json` is inert until the Renovate GitHub App is
> installed on the repository (or a self-hosted runner is configured). The
> file is harmless if the app is not installed.

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
| New HTTP route for a feature | `src/features/<feature>/adapters/inbound/http/` plus schemas and mappers as needed. |
| New use case for a feature | `src/features/<feature>/application/commands/` or `queries/`, `ports/inbound/`, and `use_cases/`. |
| New domain rule | `src/features/<feature>/domain/` and domain unit tests. |
| New persistence behavior | `src/features/<feature>/adapters/outbound/persistence/sqlmodel/` and repository contract or integration tests. |
| New database schema change | SQLModel models plus a new Alembic migration under `alembic/versions/`. |
| New cross-cutting platform behavior | `src/app_platform/` with platform tests under `src/app_platform/tests/`. |
| New feature | Recover the scaffold from git history and follow [Feature Template Guide](feature-template.md). |

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
