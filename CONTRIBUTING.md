Contributing to `starter-template-fastapi` — terse, opinionated rules for keeping the hexagonal layout, the architecture contracts, and the coverage gates green.

| Getting Started | Ways to Contribute | Development | Reference |
| --- | --- | --- | --- |
| [1. Overview](#1-overview) | [3. Reporting Bugs](#3-reporting-bugs) | [5. Development Process](#5-development-process) | [8. Naming Conventions](#8-naming-conventions) |
| [2. Quick Start](#2-quick-start) | [4. Suggesting Enhancements](#4-suggesting-enhancements) | [6. Code Quality](#6-code-quality) | [9. Deployment](#9-deployment) |
| | | [7. Testing Requirements](#7-testing-requirements) | |

<br>

# Getting Started

> Orientation and setup for new contributors.

## 1. Overview

A production-shaped FastAPI starter. Seven features ship out of the box (`authentication`, `users`, `authorization`, `email`, `background_jobs`, `file_storage`, `outbox`) on a feature-first hexagonal layout. Cross-feature calls go through ports only; Import Linter contracts in [`pyproject.toml`](pyproject.toml) enforce the boundaries.

### Prerequisites

| Tool | Version | Purpose |
| --- | --- | --- |
| Python | `3.12+` (3.14 used in dev) | Runtime |
| `uv` | latest | Dependency + venv management |
| Docker | latest | Local Postgres / Redis / integration tests |
| `make` | latest | Task runner |
| `pre-commit` | installed via `uv sync` | Git hooks |

### Related Documentation

| Doc | What's there |
| --- | --- |
| [`README.md`](README.md) | Project overview, install, common commands |
| [`docs/architecture.md`](docs/architecture.md) | Module boundaries, dependency graph, layer rules |
| [`docs/development.md`](docs/development.md) | Local workflow, Mailpit, debugging tips |
| [`docs/api.md`](docs/api.md) | Routes, schemas, status codes |
| [`docs/operations.md`](docs/operations.md) | Env-var reference, deployment, migration policy |
| [`docs/observability.md`](docs/observability.md) | Prometheus, OTel, structured logs |
| [`docs/email.md`](docs/email.md) / [`docs/background-jobs.md`](docs/background-jobs.md) / [`docs/file-storage.md`](docs/file-storage.md) / [`docs/outbox.md`](docs/outbox.md) | Per-feature deep dives |
| [`docs/feature-template.md`](docs/feature-template.md) | Recovering and renaming the feature scaffold |
| [`CLAUDE.md`](CLAUDE.md) | Architecture and conventions cheatsheet for AI agents |

### Where to get help

- File an issue on the repository's issue tracker for bugs and proposals (see [§3](#3-reporting-bugs) and [§4](#4-suggesting-enhancements)).
- For architectural questions, open an OpenSpec proposal under [`openspec/changes/`](openspec/changes/).
- <!-- TODO: add chat link (Slack / Discord) if/when one exists -->
- <!-- TODO: add maintainer contact / CODEOWNERS once defined -->

---

## 2. Quick Start

Full setup lives in [`README.md`](README.md#quick-start). One-shot for first-time contributors:

```bash
cp .env.example .env
uv sync
make precommit-install
docker compose up -d db
uv run alembic upgrade head
make dev
```

### Quick command reference

| Task | Command |
| --- | --- |
| Install deps | `make sync` |
| Run API (auto-reload) | `make dev` (override port: `make dev PORT=8080`) |
| Run worker | `make worker` (requires `APP_JOBS_BACKEND=arq`) |
| Format | `make format` |
| Lint | `make lint` (auto-fix: `make lint-fix`) |
| Architecture lint | `make lint-arch` |
| Type check | `make typecheck` |
| All quality gates | `make quality` |
| Unit + e2e tests | `make test` |
| Integration tests (Docker) | `make test-integration` |
| One feature | `make test-feature FEATURE=authentication` |
| Coverage (line + branch) | `make cov` |
| Full local CI gate | `make ci` |
| Pre-push gate (mirrors CI) | `make ci-local` |

---

<br>

# Ways to Contribute

> How to file good bug reports and feature proposals.

## 3. Reporting Bugs

### Before submitting

- [ ] Reproduce on `main` after `uv sync && uv run alembic upgrade head`.
- [ ] Check the [`openspec/changes/`](openspec/changes/) directory — your bug may be addressed by an in-flight change.
- [ ] Search existing issues for duplicates.
- [ ] Confirm it's not configuration: see [`docs/operations.md`](docs/operations.md#environment-variable-reference) and the [Troubleshooting table](README.md#troubleshooting) in the README.

### What to include

| Field | Detail |
| --- | --- |
| Environment | Python version, OS, `uv --version`, Docker version if relevant |
| Affected feature | One of `authentication`, `users`, `authorization`, `email`, `background_jobs`, `file_storage`, `outbox`, or `app_platform` |
| Reproduction | Minimal `curl` or pytest invocation; relevant `.env` values (redact secrets) |
| Observed | Status code, response body, stack trace, log lines (include `X-Request-ID`) |
| Expected | One sentence |
| Logs | Paste the JSON access log line plus any error traceback |

File at: <!-- TODO: link issue tracker, e.g. https://github.com/<org>/<repo>/issues -->

---

## 4. Suggesting Enhancements

Architectural changes go through OpenSpec, not free-form issues. The proposal lives in version control next to the code it changes.

### Before submitting

- [ ] Skim recent changes under [`openspec/changes/`](openspec/changes/) and `openspec/changes/archive/` to make sure it isn't already proposed or rejected.
- [ ] Confirm the idea respects layer and Import Linter boundaries.

### What to include

| Field | Detail |
| --- | --- |
| Problem | What hurts today, with a concrete example |
| Proposal | Smallest viable change |
| Affected ports / contracts | Which `*Port`s, tables, or Import Linter contracts move |
| Non-goals | What you're explicitly not doing |
| Migration | Backwards compat, data migration, breaking-change notes |

For non-trivial work: scaffold a change with the OpenSpec workflow (see [`openspec/`](openspec/) and the `.claude/skills/openspec-*` skills). One-line bug-fix ideas can stay as plain issues.

---

<br>

# Development

> How code lands in `main`.

## 5. Development Process

### Contribution types

| Type | Use for | Example commit subject |
| --- | --- | --- |
| `feat` | New user-visible behavior or new port/adapter | `feat(authentication): support email verification resend` |
| `fix` | Bug fix; no behavior gained | `fix(outbox): claim batch respects max_attempts` |
| `refactor` | Internal restructuring; no behavior change | `refactor(authorization): extract registry sealing` |
| `perf` | Measurable performance improvement | `perf(users): index users.email lower()` |
| `docs` | Docs / comments only | `docs(operations): document one-way migration policy` |
| `test` | Test-only changes | `test(email): add SMTP STARTTLS contract` |
| `chore` | Dependency bumps, tooling, repo housekeeping | `chore(deps): bump ruff to 0.14.0` |
| `ci` | CI workflow changes | `ci: pin actions to commit SHAs` |

A trailing `!` (e.g. `refactor!:`) marks a breaking change. See [Breaking changes](#breaking-changes) below.

### Branch naming

Trunk-based: branch from `main`, PR back to `main`. No long-lived branches.

```
<type>/<short-kebab-description>
```

| Good | Bad |
| --- | --- |
| `feat/email-verification-resend` | `stevens-branch` |
| `fix/outbox-claim-batch` | `wip` |
| `refactor/users-extract-port` | `branch-1` |
| `chore/bump-ruff` | `feature/long-descriptive-name-with-ticket-id-everything` |

### Commit messages

[Conventional Commits](https://www.conventionalcommits.org/). The repo's history is dominated by `feat`, `fix`, `refactor`, `chore`, `ci` — match that vocabulary.

```text
# Good
feat(authentication): rotate refresh token on each use
fix(outbox): retry exhausted rows must flip to failed, not pending
refactor!: adopt canonical src layout (drop src. prefix)

# Bad
updates                 # what changed?
fix bug                 # which bug?
WIP                     # not a commit message
```

Body (optional, separated by a blank line) explains *why* and any non-obvious trade-offs. Reference an OpenSpec change directory or issue number when relevant.

### Pull requests

| Field | Expectation |
| --- | --- |
| Title | Same shape as a commit subject; one Conventional Commit type |
| Description | What changed, why, what you tested. Link the OpenSpec change directory if any. |
| Scope | One topic per PR. Split unrelated drive-by edits. |
| Size | Aim for < 400 lines of diff excluding lockfile / generated migrations. |
| Status checks | All required jobs in `.github/workflows/ci.yml` must pass — `quality`, `tests`, `audit`, `sast`, `integration`, `migrations`, `docker`, aggregated as `ci-gate`. |
| Migrations | Run `uv run alembic check` locally; a destructive downgrade must `raise NotImplementedError` (see [`docs/operations.md`](docs/operations.md) — one-way migration policy). |
| Review | <!-- TODO: document review process and minimum approver count once codified --> |

### Git best practices

#### DO ✅

- Rebase onto the latest `main` before opening a PR (`git fetch origin && git rebase origin/main`).
- Squash WIP commits locally; keep the PR's final commits meaningful.
- Run `make ci-local` before pushing — it mirrors the CI jobs and catches problems before the runner does.
- Delete your branch after merge.

#### DON'T ❌

- Don't force-push to `main`.
- Don't merge `main` *into* your branch — rebase instead. Merge commits clutter history.
  - ❌ `git merge main`
  - ✅ `git rebase origin/main`
- Don't commit `.env`, `reports/`, `.coverage`, or generated `htmlcov/` (already in `.gitignore`).
- Don't commit secrets — `gitleaks` runs in CI and will fail the build (config: [`.gitleaks.toml`](.gitleaks.toml)).

### Breaking changes

A change is breaking if it removes or alters a public route, an environment variable, an `ApplicationError` subclass on the wire, a port signature consumed by another feature, or a database column without a migration. Mark it with `!` in the commit subject (`feat!:` / `refactor!:`) and document it in the PR description and the OpenSpec change.

---

## 6. Code Quality

### Principles

| Principle | What it means here |
| --- | --- |
| **Hexagonal layering** | `domain → application → adapters → composition`. Inner layers never import outer ones. Enforced by Import Linter. |
| **Ports over imports** | Cross-feature calls always go through an application port; never `from features.x.adapters import ...`. |
| **Result, not raise** | Use cases return `Result[T, ApplicationError]`. Exceptions are for *exceptional* failures, not control flow. |
| **Composition at the edge** | Concrete adapters are wired in `composition/container.py` and `src/main.py` / `src/worker.py` — never instantiated inside use cases. |
| **One-way migrations are explicit** | Destructive Alembic downgrades raise `NotImplementedError`. See [`docs/operations.md`](docs/operations.md). |

### Linting & formatting

Configured in [`pyproject.toml`](pyproject.toml) (`[tool.ruff]`, `[tool.mypy]`, `[tool.importlinter]`).

| Task | Command |
| --- | --- |
| Format | `make format` (Ruff formatter) |
| Lint | `make lint` (Ruff check) |
| Lint with auto-fix | `make lint-fix` |
| Architecture contracts | `make lint-arch` (Import Linter) |
| Type check | `make typecheck` (mypy strict) |
| Run all gates | `make quality` |

Pre-commit hooks (installed via `make precommit-install`) run `ruff format` and `ruff check --fix` on every commit, and `make ci-local` on every push. Config: [`.pre-commit-config.yaml`](.pre-commit-config.yaml).

### Security

#### DO ✅

- Use the existing `argon2-cffi` hasher for any new secret-at-rest. Never roll your own.
- Read secrets through `AppSettings` (`APP_`-prefixed env vars). Never hard-code.
- Use parameterized SQLModel / SQLAlchemy queries. The existing repos already do — match that.
- Add a Bandit `# nosec` only with a one-line comment explaining *why* the finding is safe.

#### DON'T ❌

- Don't commit `.env`, API keys, or test fixtures with real credentials.
  - ❌ `JWT_SECRET = "dev-key-1234"` checked in
  - ✅ `JWT_SECRET = os.environ["APP_AUTH_JWT_SECRET_KEY"]`
- Don't disable Ruff `S` (security) rules globally — file-scoped `per-file-ignores` exist for tests only.
- Don't bypass `require_authorization(...)` on a write route. If the route legitimately doesn't need auth, document it in the route docstring.
- Don't catch `Exception` to convert it to `Ok(...)`. If a use case can fail, model the failure as an `ApplicationError`.

### Python style

- **Type hints everywhere.** mypy runs in strict mode (`disallow_untyped_defs`, `no_implicit_optional`); untyped functions fail CI.
- **`Annotated` aliases for FastAPI dependencies** — see existing `*Dep` names in `adapters/inbound/http/dependencies.py`.
- **`@dataclass(slots=True)`** for use cases and mutable domain entities; `@dataclass(frozen=True, slots=True)` for commands, queries, and read contracts.
- **Logging via `logging.getLogger(__name__)`** at module top, not via `print`. Error logs include the request ID where available.
- **Errors must be picklable** — `ApplicationError` subclasses round-trip through Redis (arq). If a class needs non-positional args, implement `__reduce__`. See [`src/app_platform/shared/tests/unit/test_application_error_pickling.py`](src/app_platform/shared/tests/unit/test_application_error_pickling.py).
- **Line length: 88** (Ruff default).
- **Target `py312`** — don't use 3.13/3.14-only syntax in committed code; the lockfile and CI run on 3.12.

### Comments & Docstrings

These are non-negotiable conventions, not suggestions. They apply to every file under `src/`, `tests/`, `alembic/`, and `scripts/`.

#### Rule 1 — File-path header comment

Every source file begins with a `#` comment showing its path from the repo root. First line of the file, *before* any docstring, `from __future__` import, or other content. Test files use their own path, not the path of the file under test.

```python
# src/features/authentication/application/use_cases/auth/request_email_verification.py
"""
Issues an email-verification token alongside an outbox row so the
delivery and the audit event commit atomically.
"""
from __future__ import annotations
```

For shell scripts, keep the shebang on line 1 and the path comment on line 2:

```bash
#!/usr/bin/env bash
# scripts/migration-check.sh
```

For SQL or other languages, use that language's line-comment syntax (`--` for SQL, `//` for any future TS/JS). The rule applies analogously to every committed source file.

**Why this matters**

- Quick navigation in a feature-first repo where many files are named `container.py`, `adapter.py`, `errors.py`, `models.py`, `conftest.py`.
- Disambiguates similarly-named files across features (`composition/container.py` exists in seven places).
- Copy-paste safety — pasting a snippet into chat or an issue keeps its provenance.

#### Rule 2 — Docstrings explain WHY, not WHAT

2–5 lines maximum. Describe intent, trade-offs, or non-obvious context — not a paraphrase of the function signature. If the docstring only restates the name and parameters, delete it.

```python
# Good (explains why)
def claim_pending(self, *, batch_size: int) -> list[OutboxRow]:
    """
    Claim a batch with SKIP LOCKED so concurrent relays do not double-dispatch.
    Rows that exhaust APP_OUTBOX_MAX_ATTEMPTS are flipped to ``failed`` here, not by the caller.
    """
```

```python
# Bad (restates code)
def claim_pending(self, *, batch_size: int) -> list[OutboxRow]:
    """Claims pending outbox rows up to batch_size and returns them."""
```

#### Rule 3 — Inline comments: explain intent, not mechanics

Comments answer "why is this here?" — never "what does this line do?" If a block needs a comment to be understandable, first try renaming variables or extracting a helper. Comment only if that fails. Prefer one comment above a block over comments on every line.

```python
# Good
# Read APP_POSTGRESQL_DSN before AppSettings so Alembic uses the same
# DSN as the running app even when the env var overrides defaults.
dsn = os.environ.get("APP_POSTGRESQL_DSN") or AppSettings().postgresql_dsn
```

```python
# Bad
# Get the DSN from environment
dsn = os.environ.get("APP_POSTGRESQL_DSN") or AppSettings().postgresql_dsn
```

#### Rule 4 — TODO / FIXME / NOTE / HACK markers

Format: `# <MARKER>(handle): <description> [ticket-id]`. Author handle and ticket reference are required. Bare `# TODO: fix later` will fail review.

| Marker | Meaning |
| --- | --- |
| `TODO` | Planned work that hasn't been done yet |
| `FIXME` | Known bug or wrong behavior; the surrounding code still ships |
| `HACK` | Workaround that should be revisited; explain the constraint |
| `NOTE` | Important context that isn't obvious from the code itself |

```python
# TODO(alice): switch to batched lookup once UserPort.get_many lands [PROJ-1234]
# FIXME(bob): race condition when two tabs refresh simultaneously [PROJ-1289]
# HACK(carol): pin urllib3 < 3 until httpx upgrades [PROJ-1301]
# NOTE: the cache TTL bounds revocation lag — see docs/operations.md.
```

#### Rule 5 — What NOT to comment

- Don't comment out dead code — delete it. Git remembers.
- Don't write banner comments for every section of a file (`### HELPERS ###`). If a file needs banners it's too big — split it.
- Don't restate type information the annotations already convey.
- Don't leave commented-out `print(...)` or `logger.debug(...)` lines. Use the logger at `debug` level if you need it again.

#### Rule 6 — Module / file-level docstring

The line under the path comment is one short paragraph (1–3 sentences) describing the file's responsibility. It should answer: *"If I delete this file, what capability disappears?"* Not a changelog. Not a list of exports. Not author/date metadata — git tracks that.

```python
# src/features/outbox/application/use_cases/dispatch_pending.py
"""
Drains the outbox by claiming a batch under SKIP LOCKED and dispatching
each row through ``JobQueuePort``. The relay is the only consumer of the
outbox table; producers write rows inside their own UoW transactions.
"""
```

---

## 7. Testing Requirements

### Test pyramid

| Layer | Marker | Where | Speed | Coverage target |
| --- | --- | --- | --- | --- |
| Unit | `unit` | `src/<package>/tests/unit/` | Milliseconds | Most behavior — pure logic, ports, error mapping |
| Contract | (none — invoked by unit + integration) | `src/features/<feature>/tests/contracts/` | Fast | Same assertions run against fakes and real adapters |
| End-to-end | `e2e` | `src/features/<feature>/tests/e2e/` | Sub-second | Happy path + key error paths through FastAPI with in-memory fakes |
| Integration | `integration` | `src/features/<feature>/tests/integration/` | Seconds (Docker) | Persistence, transactions, real Postgres / Redis behavior |

Aggregate gates enforced by `make ci`:

| Gate | Floor | Where configured |
| --- | --- | --- |
| Statement (line) coverage | **80%** | `[tool.coverage.report] fail_under` in [`pyproject.toml`](pyproject.toml) |
| Branch coverage | **60%** | `BRANCH_COVERAGE_FLOOR` in [`Makefile`](Makefile) — override with `BRANCH_COVERAGE_FLOOR=70 make cov` |

### Commands

| Task | Command |
| --- | --- |
| All non-Docker tests | `make test` |
| Docker-backed integration | `make test-integration` |
| End-to-end only | `make test-e2e` |
| One feature | `make test-feature FEATURE=authentication` |
| One file | `uv run pytest src/features/authentication/tests/e2e/test_auth_flow.py` |
| Coverage with line + branch gate | `make cov` |
| HTML coverage report | `make cov-html` (output: `reports/coverage/index.html`) |
| Skip testcontainers | `KANBAN_SKIP_TESTCONTAINERS=1 make test-integration` |

### Writing a test

#### Where it goes

| Test type | File location | Naming |
| --- | --- | --- |
| Unit | `src/<package>/tests/unit/test_<subject>.py` | `test_*` |
| Contract | `src/features/<feature>/tests/contracts/test_<port>_contract.py` | One module per port |
| End-to-end | `src/features/<feature>/tests/e2e/test_<flow>.py` | One module per HTTP flow |
| Integration | `src/features/<feature>/tests/integration/test_<adapter>.py` | One module per adapter |

#### Markers

```python
# src/features/email/tests/unit/test_template_registry.py
import pytest

pytestmark = pytest.mark.unit


def test_registry_seals_after_main_app_starts() -> None:
    ...
```

```python
# src/features/users/tests/integration/test_sqlmodel_user_repository.py
import pytest

pytestmark = pytest.mark.integration


def test_user_email_unique_constraint(pg_engine) -> None:
    ...
```

Markers are strict (`--strict-markers` in `[tool.pytest.ini_options]`). Only `unit`, `integration`, `e2e` are registered — adding a new one means updating `pyproject.toml`.

#### Fakes vs real adapters

- Use the per-feature **fakes** under `src/features/<feature>/tests/fakes/` for unit and e2e tests. They live next to the production code that defines the port.
- Use **testcontainers** (`pg_engine` fixture and friends) for integration tests. Real Postgres, real transactions, real `RETURNING` semantics.
- Reuse the **contract** test suites (`tests/contracts/`) against both — that's how we keep fakes honest.

#### Async

`asyncio_mode = "auto"`. Mark async tests with `async def test_...`; pytest-asyncio handles the loop.

---

<br>

# Reference

> Tables to look up while writing code.

## 8. Naming Conventions

| What | Convention | Example |
| --- | --- | --- |
| Module / file | `snake_case.py` | `request_email_verification.py` |
| Package / directory | `snake_case` | `background_jobs/`, `application/use_cases/` |
| Class | `PascalCase` | `RotateRefreshToken`, `OutboxRow` |
| Function / method | `snake_case` | `claim_pending`, `issue_internal_token_transaction` |
| Constant | `UPPER_SNAKE_CASE` | `SEND_EMAIL_JOB`, `VERIFY_EMAIL_TEMPLATE` |
| Private name | leading `_` | `_logger`, `_verify_url(...)` |
| Type alias / `TypeVar` | `PascalCase`, single-letter or descriptive | `Result[T, E]`, `UserPort` |
| Application port | `<Capability>Port` | `JobQueuePort`, `OutboxPort`, `UserPort` |
| Use case class | Verb phrase | `RegisterUser`, `DispatchPending` |
| SQL table | `snake_case`, plural | `users`, `credentials`, `outbox_messages`, `relationships` |
| Env var | `APP_` prefix, `UPPER_SNAKE_CASE` | `APP_AUTH_JWT_SECRET_KEY`, `APP_OUTBOX_ENABLED` |
| Alembic revision | autogenerated id + `<verb>_<noun>` slug | `add_outbox_messages_table` |
| Branch | `<type>/<short-kebab>` | `feat/email-verification-resend` |

---

## 9. Deployment

This is a starter template, not a deployed service — the deployment target depends on the project that adopts it. Use [`docs/operations.md`](docs/operations.md) as the source of truth.

### Pre-deploy checklist

- [ ] `make ci` passes locally.
- [ ] `APP_ENVIRONMENT=production` is set; the production validator refuses to start with `*` CORS, `console` email, `in_process` jobs, insecure cookies, RBAC disabled, `auth_return_internal_tokens=true`, or `APP_OUTBOX_ENABLED=false`. Full list: [`docs/operations.md` § Environment Variable Reference](docs/operations.md#environment-variable-reference).
- [ ] `APP_AUTH_JWT_SECRET_KEY` (≥ 32 chars), `APP_AUTH_JWT_ISSUER`, `APP_AUTH_JWT_AUDIENCE` set.
- [ ] `APP_POSTGRESQL_DSN` and `APP_AUTH_REDIS_URL` (or `APP_JOBS_REDIS_URL`) reachable.
- [ ] `uv run alembic upgrade head` runs as a separate deploy step *before* the API container starts.
- [ ] Email backend is `smtp` or `resend` with credentials set.
- [ ] At least one worker (`python -m worker`) is running per Redis-backed deployment — the API does not consume the job queue.
- [ ] Liveness / readiness probes wired to `/health/live` and `/health/ready`.

### Runtime image

```bash
docker build --target runtime -t starter-template-fastapi:prod .
docker run --rm --env-file .env starter-template-fastapi:prod alembic upgrade head
docker run --env-file .env -p 8000:8000 starter-template-fastapi:prod
docker run --env-file .env starter-template-fastapi:prod python -m worker
```

<!-- TODO: document target environments (staging / production hosts, IaC repo, deploy command) once the project hosting this template defines them -->
