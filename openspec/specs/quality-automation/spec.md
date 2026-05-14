# quality-automation Specification

## Purpose
TBD - created by archiving change add-quality-automation. Update Purpose after archive.
## Requirements
### Requirement: Branch coverage measured and gated

The system SHALL measure branch coverage in addition to line coverage during every `make cov`, `make cov-html`, `make cov-xml`, and `make ci` invocation, and SHALL gate `make ci` on both a line-coverage floor and a branch-coverage floor. The branch-coverage floor SHALL be configured in the `Makefile` as `BRANCH_COVERAGE_FLOOR` and SHALL be set, at the time of introduction, to the value the current `main` branch achieves rounded down to the nearest 5%. The branch-coverage floor SHALL be overrideable per-invocation via an environment variable of the same name.

#### Scenario: `make ci` fails when branch coverage drops below floor

- **WHEN** a developer runs `make ci` and the resulting branch-coverage percentage is below the configured branch floor
- **THEN** `make ci` exits with a non-zero status and the failure message identifies branch coverage (not line coverage) as the cause

#### Scenario: `make ci` fails when line coverage drops below floor

- **WHEN** a developer runs `make ci` and the resulting line-coverage percentage is below the configured 80% line floor
- **THEN** `make ci` exits with a non-zero status and the failure message identifies line coverage as the cause

#### Scenario: Coverage targets emit branch data

- **WHEN** a developer runs `make cov`, `make cov-html`, or `make cov-xml`
- **THEN** the resulting `reports/coverage.json` contains a `totals.percent_branches_covered` field with a numeric value

#### Scenario: Coverage report shows both numbers

- **WHEN** a developer runs `make cov`
- **THEN** the terminal output prints both line-coverage and branch-coverage totals, and the per-file table includes branch columns

#### Scenario: Floor is overrideable via environment variable

- **WHEN** a developer runs `BRANCH_COVERAGE_FLOOR=95 make cov` and the actual branch coverage is below 95%
- **THEN** the command exits with a non-zero status and the failure message names the override value

#### Scenario: `make ci` runs through `make cov`, not `make test`

- **WHEN** an operator inspects the `Makefile`
- **THEN** the `ci` target's prerequisites include `cov` (not `test`), and the `ci-local` target's prerequisites also include `cov`

#### Scenario: GitHub `tests` job runs the coverage gate

- **WHEN** an operator inspects `.github/workflows/ci.yml`
- **THEN** the `tests` job invokes `make cov` (not `make test`), so the coverage floors are enforced on every CI run

### Requirement: Renovate manages Python and GitHub Actions dependencies

The system SHALL ship a `renovate.json` configuration at the repository root that enables Renovate to open update pull requests for Python dependencies tracked in `pyproject.toml` / `uv.lock` and for GitHub Actions referenced in `.github/workflows/*.yml`. The repository SHALL NOT ship a Dependabot configuration.

#### Scenario: Renovate config exists at repo root

- **WHEN** an operator inspects the repository root
- **THEN** a file named `renovate.json` exists, is valid JSON, and extends `config:recommended`

#### Scenario: No Dependabot config exists

- **WHEN** an operator inspects `.github/`
- **THEN** no `dependabot.yml` (or `dependabot.yaml`) file is present

#### Scenario: Co-versioned package groups are declared

- **WHEN** an operator inspects `renovate.json`
- **THEN** `packageRules` declares update groups that include at minimum: `pytest` + `pytest-*`, `fastapi` + `starlette` + `pydantic` + `pydantic-settings`, `sqlmodel` + `sqlalchemy` + `alembic`, `arq` + `redis`, and `boto3` + `botocore`

#### Scenario: PR-rate limits prevent firehose

- **WHEN** Renovate is freshly enabled against the repository
- **THEN** `renovate.json` declares `prConcurrentLimit` and `prHourlyLimit` values that bound how many update PRs may be open or opened per hour, and a Dependency Dashboard issue is enabled

#### Scenario: Lockfile maintenance is scheduled weekly

- **WHEN** an operator inspects `renovate.json`
- **THEN** `lockFileMaintenance` is enabled with an explicit weekly schedule

### Requirement: GitHub Actions are pinned to SHAs for Renovate to maintain

The system SHALL pin every `uses:` reference in `.github/workflows/*.yml` to a full commit SHA, with a trailing comment noting the human-readable version tag, so that Renovate can update them deterministically and reviewers can still read intended versions.

#### Scenario: Every workflow action is pinned to a SHA

- **WHEN** an operator inspects every `.github/workflows/*.yml` file
- **THEN** every `uses:` value references either a 40-character commit SHA or a local action path; no `uses:` references a floating tag or branch (e.g. `@v4`, `@main`)

#### Scenario: SHA pin includes a version comment

- **WHEN** an operator inspects any pinned `uses:` line
- **THEN** the line carries a trailing comment of the form `# <version-tag>` indicating the intended semantic version

#### Scenario: Renovate is configured to bump action SHAs

- **WHEN** an operator inspects `renovate.json`
- **THEN** the `github-actions` manager is enabled and `pinDigests` (or the equivalent setting) applies to it

### Requirement: Documentation reflects the new gates

The system SHALL document the new commands, gates, and dependency-update policy in `docs/development.md`, the project `README.md`, and `CLAUDE.md`'s Commands table so contributors discover them without reading CI files.

#### Scenario: Quality gates documented in development docs

- **WHEN** a contributor reads `docs/development.md`
- **THEN** a "Quality Gates" section describes that `make ci` enforces both a line-coverage floor and a branch-coverage floor, names the current thresholds, and explains how to override `BRANCH_COVERAGE_FLOOR`

#### Scenario: Dependency update policy documented

- **WHEN** a contributor reads `docs/development.md`
- **THEN** a "Dependency Updates" section explains Renovate's grouped PR cadence, lockfile-maintenance schedule, Dependency Dashboard issue, and SHA-pinning convention for workflow files

#### Scenario: Commands table reflects the new wiring

- **WHEN** a contributor reads `CLAUDE.md` and `README.md`
- **THEN** both Commands tables describe `make cov` as gating both line and branch coverage, and `make ci` as the full quality + coverage + integration gate

### Requirement: Documented setup sequence boots a runnable dev server on a clean checkout

The repository SHALL ship dev dependencies and example configuration such that the documented Setup-and-Development command sequence in `CLAUDE.md` produces a runnable FastAPI server with no further manual edits required.

Concretely, after running the documented sequence from a fresh clone (`cp .env.example .env`, `uv sync`, `docker compose up -d db`, `uv run alembic upgrade head`, `make dev`):

- The `fastapi` CLI binary used by `make dev` MUST be installed by `uv sync` (i.e. `fastapi[standard]` MUST be declared in the `dev` dependency group of `pyproject.toml`).
- The FastAPI lifespan startup MUST complete successfully — no required env var raised by any feature's composition root may be unset in `.env.example`. In particular, `APP_STORAGE_LOCAL_PATH` MUST have a default value in `.env.example` because `build_file_storage_container` requires it when `APP_STORAGE_BACKEND=local` (the default backend).
- The default storage path provided in `.env.example` MUST point inside the repo (e.g. `./var/storage`), and the parent directory pattern MUST be covered by `.gitignore`.

#### Scenario: `uv sync` installs the `fastapi` CLI binary

- **GIVEN** a fresh checkout
- **WHEN** the contributor runs `uv sync`
- **THEN** `uv run fastapi --version` exits with status 0 and prints a version string

#### Scenario: `make dev` boots without manual `.env` edits

- **GIVEN** a fresh checkout with the documented setup sequence completed (`cp .env.example .env && uv sync && docker compose up -d db && uv run alembic upgrade head`)
- **WHEN** the contributor runs `make dev`
- **THEN** the process logs `Uvicorn running on http://0.0.0.0:8000` (or the configured port) within the startup-timeout budget
- **AND** the process does not log any `RuntimeError` from a feature composition root
- **AND** in particular it does not raise `APP_STORAGE_LOCAL_PATH is required when APP_STORAGE_BACKEND=local`

#### Scenario: Default storage path is repo-local and ignored by git

- **GIVEN** the value of `APP_STORAGE_LOCAL_PATH` from a freshly copied `.env.example`
- **WHEN** the path is resolved against the repo root
- **THEN** it points inside the repository working tree (e.g. `./var/storage`)
- **AND** `git status` after a boot that wrote to that path lists no untracked files under that directory (the path or its parent is covered by `.gitignore`)

### Requirement: Renovate fast-tracks security alerts and tracks pre-commit hooks

`renovate.json` SHALL include a `vulnerabilityAlerts` block enabling immediate PR creation for security advisories with `automerge: true` for non-major bumps. It SHALL enable the `pre-commit` manager so hook versions in `.pre-commit-config.yaml` are tracked. It SHALL define grouping rules for production deps, dev deps, and pre-commit hooks, plus a weekly Monday `lockfileMaintenance` schedule.

#### Scenario: Security advisory produces an immediate PR

- **GIVEN** a transitive dep gains a HIGH-severity advisory
- **WHEN** Renovate next polls (or via the alert webhook)
- **THEN** a PR is opened with label `security` and the rate limits / regular grouping rules do not delay it
- **AND** the PR is set to auto-merge if it is a patch or minor bump and CI is green

#### Scenario: Major-version security bump requires human review

- **GIVEN** a security advisory whose fix is a major-version bump
- **WHEN** Renovate opens the PR
- **THEN** the PR is labelled `security` but `automerge` is false
- **AND** the PR sits open until a maintainer approves it

#### Scenario: pre-commit hook bump produces a grouped PR

- **GIVEN** `pre-commit-hooks v6.1.0` is released
- **WHEN** Renovate's next weekly run executes
- **THEN** a PR is opened to bump the hook in `.pre-commit-config.yaml`
- **AND** the PR is part of the `pre-commit-hooks` group

#### Scenario: Weekly Monday lockfile maintenance lands in one window

- **GIVEN** the calendar reaches Monday 09:00 UTC
- **WHEN** Renovate runs
- **THEN** at most one lockfile-maintenance PR is open at any time and it lands within that window

### Requirement: Ruff lint covers security, modernization, async, performance, and idiom rules

`[tool.ruff.lint] select` in `pyproject.toml` SHALL include at minimum `["E","F","I","B","UP","S","C4","RUF","SIM","PT","TRY","RET","ARG","DTZ","ASYNC","PERF","PL"]`. `[tool.ruff.lint.per-file-ignores]` SHALL relax test-relevant rules (`S101`, `S105`, `S106`, `ARG`, `PLR2004`) under `**/tests/**` and `**/conftest.py`. Autogenerated `alembic/versions/*.py` SHALL be excluded with `["ALL"]`. SQLModel model modules SHALL be excluded from `RUF012`.

Project-wide `extend-ignore` SHALL document the rationale for any rule it silences (currently `TRY003`, `PLC0415`).

#### Scenario: A naive datetime usage is rejected

- **GIVEN** non-test code adds `datetime.now()` with no tz argument
- **WHEN** `make lint` runs
- **THEN** ruff fails with `DTZ005`

#### Scenario: `time.sleep` inside `async def` is rejected

- **GIVEN** non-test code calls `time.sleep(...)` inside an `async def`
- **WHEN** `make lint` runs
- **THEN** ruff fails with `ASYNC101` (or the current ASYNC code for blocking sleep)

#### Scenario: `assert` is allowed in tests but rejected in `src/`

- **GIVEN** a test under `src/features/<f>/tests/unit/` uses `assert x == 1`
- **WHEN** `make lint` runs
- **THEN** ruff is silent (per-file-ignore `S101` applies)
- **AND** the same `assert` in non-test code under `src/` would fail with `S101`

#### Scenario: SQLModel class-default mutable is allowed only under the models path

- **GIVEN** a SQLModel table at `src/features/<f>/adapters/outbound/persistence/sqlmodel/models.py` uses `metadata = {...}` as a class attribute
- **WHEN** `make lint` runs
- **THEN** ruff is silent (per-file-ignore `RUF012` applies)
- **AND** the same pattern in a non-model file would fail with `RUF012`

### Requirement: Type checking is strict

`[tool.mypy]` in `pyproject.toml` SHALL set `strict = true`. `make typecheck` SHALL pass with no `# type: ignore` lacking an inline `XXX:` reason comment. Per-module `ignore_missing_imports` overrides are permitted only for genuinely untyped third-party packages and SHALL carry a comment naming the package.

#### Scenario: Strict mode rejects an implicit Any return

- **GIVEN** the codebase with `strict = true` enabled in `pyproject.toml`
- **WHEN** a contributor adds a function whose return type is inferred as `Any` and assigns its result to a `str` variable
- **THEN** `make typecheck` exits non-zero with a clear `[no-any-return]` or `[assignment]` diagnostic

#### Scenario: A `# type: ignore` without a reason fails review

- **GIVEN** a PR adds a bare `# type: ignore[attr-defined]` with no trailing reason comment
- **WHEN** `make typecheck` runs
- **THEN** the gate still passes (mypy accepts the ignore), but the spec marks this as non-compliant and the reviewer rejects the diff

#### Scenario: An unused ignore is flagged

- **GIVEN** a previously needed `# type: ignore[attr-defined]` whose underlying error has been fixed
- **WHEN** `make typecheck` runs under `strict = true`
- **THEN** mypy reports `[unused-ignore]` and the gate fails

### Requirement: docker-compose provides an SMTP catcher for dev

`docker-compose.yml` SHALL include a `mailpit` service exposing SMTP on `1025` and the UI on `8025`. `.env.example` SHALL include commented env-var examples wiring the SMTP backend to the catcher.

The `app` service SHALL declare `restart: unless-stopped` and a `healthcheck` hitting `/health/live`.

#### Scenario: Mailpit catches a password-reset email

- **GIVEN** a developer runs `docker compose up` and switches `APP_EMAIL_BACKEND=smtp` + `APP_EMAIL_SMTP_HOST=mailpit`
- **WHEN** the developer triggers a password reset
- **THEN** the email appears in the Mailpit UI at `http://localhost:8025`

#### Scenario: App service marked unhealthy when /health/live fails

- **GIVEN** the `app` service is up but its `/health/live` endpoint returns a non-200 response (e.g. lifespan startup raised)
- **WHEN** the compose healthcheck retries past the configured `retries` budget
- **THEN** `docker compose ps` reports the `app` service as `unhealthy`
- **AND** the `restart: unless-stopped` policy attempts to restart it

#### Scenario: Default backend is unchanged

- **GIVEN** a developer runs `docker compose up` without overriding `APP_EMAIL_BACKEND`
- **WHEN** the API sends an email
- **THEN** the email is routed via the console backend (printed to stdout)
- **AND** no SMTP connection to the `mailpit` service is opened

### Requirement: CI scans the built container image and produces an SBOM

CI SHALL build the production image and run Trivy (or equivalent) with `severity=HIGH,CRITICAL` and `exit-code=1`. A SBOM (SPDX or CycloneDX JSON) SHALL be generated for the same image and uploaded as a workflow artifact. PRs SHALL also run `actions/dependency-review-action` with `fail-on-severity: high`.

The workflow SHALL declare `permissions: { contents: read }` at the top level; per-job elevations are explicit.

All `uses:` references SHALL be pinned by commit SHA (with a version comment).

#### Scenario: CRITICAL CVE in base image fails the build

- **GIVEN** a Trivy run that detects a CRITICAL vulnerability in the runtime image
- **WHEN** the job completes
- **THEN** the job exits non-zero and the PR check is failed

#### Scenario: PR adds a HIGH-severity dependency

- **GIVEN** a PR that introduces a transitive dep with a HIGH-severity advisory
- **WHEN** `dependency-review` runs
- **THEN** the check is failed with a clear message naming the dep

#### Scenario: A PR removes or skips the Trivy/SBOM gate

- **GIVEN** a PR that deletes the Trivy or SBOM step from `.github/workflows/ci.yml`, or sets `continue-on-error: true` on it
- **WHEN** CI runs on that PR
- **THEN** the workflow fails because the required `image-scan` / `sbom` job (or step output) is missing or did not enforce its exit code
- **AND** the failure message names the missing gate

#### Scenario: An unpinned action reference is rejected

- **GIVEN** a PR that adds `uses: org/action@v4` (tag) instead of a commit SHA
- **WHEN** CI runs
- **THEN** the workflow's pin-check step (or `dependency-review-action`'s action pinning policy) fails the build with the unpinned reference named in the log

### Requirement: Strategic `Any`/`object` hotspots are typed

The `_principal_from_user` helper in `src/features/authentication/application/use_cases/auth/refresh_token.py` SHALL accept a `UserSnapshot` Protocol parameter (not `object`). The arq `WorkerSettings` class in `src/worker.py` SHALL declare typed class attributes for every field it actually uses (`functions`, `cron_jobs`, `redis_settings`, `on_startup`, `on_shutdown`, `queue_name`). The cron-job builders SHALL return `Sequence[CronJob]`, not `Sequence[Any]`.

#### Scenario: No silenced attribute-error ignores remain in `refresh_token.py`

- **GIVEN** the codebase after this change lands
- **WHEN** `rg "type: ignore\[attr-defined\]" src/features/authentication/application/use_cases/auth/refresh_token.py` runs
- **THEN** there are zero matches

#### Scenario: WorkerSettings exposes typed attributes

- **GIVEN** the codebase after this change lands
- **WHEN** a contributor introspects `WorkerSettings` via `inspect.get_annotations(WorkerSettings)`
- **THEN** the returned dict contains entries for `functions`, `cron_jobs`, `redis_settings`, `on_startup`, `on_shutdown`, `queue_name`
- **AND** the call site `arq.run_worker(WorkerSettings)` no longer needs an `Any` cast

#### Scenario: CronJob sequences are typed

- **GIVEN** `src/features/outbox/composition/worker.py:build_relay_cron_jobs`
- **WHEN** mypy checks the file under strict mode
- **THEN** the return annotation is `Sequence[CronJob]` (not `Sequence[Any]`)
- **AND** no `# type: ignore` is needed at any call site

#### Scenario: Passing a non-conforming object to `_principal_from_user` fails type-check

- **GIVEN** a hypothetical caller that passes an object lacking `authz_version` to `_principal_from_user`
- **WHEN** mypy checks the caller under strict mode
- **THEN** mypy reports a structural-protocol violation against `UserSnapshot`
- **AND** the failure surfaces at the call site, not inside `_principal_from_user` (so no new `# type: ignore` is needed there)

### Requirement: Runtime dependencies are split into `core`, `api`, `worker`, and adapter extras

`pyproject.toml` `[project] dependencies` SHALL contain only the cross-cutting deps every layer needs (the **core** set). Role-specific deps SHALL live in `[project.optional-dependencies]`:

- `api` — `fastapi[standard]` and anything else only the API process needs.
- `worker` — `arq`, `redis`, and anything else only the background worker needs.
- `resend` — `httpx` for the Resend email adapter.
- `s3` — `boto3` for the S3 file-storage adapter.

`python-multipart` SHALL appear in exactly one place (transitively via `fastapi[standard]` in the `api` extra), not as a direct dependency.

The Resend adapter's composition SHALL raise a clear startup error referencing the `resend` extra when `httpx` is missing. The S3 adapter SHALL do the same for `boto3` and the `s3` extra.

#### Scenario: Default install lacks role-specific deps

- **GIVEN** a fresh `uv sync` with no extras
- **WHEN** the user inspects `uv pip list`
- **THEN** `httpx`, `fastapi`, `arq`, and `boto3` are all absent
- **AND** `uv.lock` resolves successfully (the core set installs cleanly)

#### Scenario: API role install brings only the API deps

- **GIVEN** `uv sync --extra api`
- **WHEN** the user inspects the resolved install
- **THEN** `fastapi[standard]` and (transitively) `python-multipart` are present
- **AND** `arq` and `redis` are absent

#### Scenario: Worker role install brings only the worker deps

- **GIVEN** `uv sync --extra worker`
- **WHEN** the user inspects the resolved install
- **THEN** `arq` and `redis` are present
- **AND** `fastapi[standard]` is absent

#### Scenario: Resend extra brings httpx

- **GIVEN** `uv sync --extra api --extra resend`
- **WHEN** the API process starts with `APP_EMAIL_BACKEND=resend`
- **THEN** `httpx` is in the resolved install
- **AND** the Resend adapter composes successfully

#### Scenario: Missing extra produces a clear startup error

- **GIVEN** `uv sync --extra api` (no `resend` extra) and `APP_EMAIL_BACKEND=resend`
- **WHEN** the app starts
- **THEN** composition fails with an error message naming the `resend` extra (e.g. `"install with: uv sync --extra resend"`)
- **AND** the app does not silently start without an email transport

### Requirement: CI caches uv installs and publishes coverage artifacts

CI SHALL enable the `setup-uv` wheel cache on every job that runs `uv sync`. After `make cov`, the workflow SHALL upload `reports/coverage.json` and `reports/coverage.xml` as a single workflow artifact named `coverage`.

#### Scenario: Coverage artifact is published

- **GIVEN** a PR triggers the CI workflow
- **WHEN** the `cov` job finishes successfully
- **THEN** the workflow run summary lists a `coverage` artifact whose payload contains `coverage.json` and `coverage.xml`

#### Scenario: uv cache is keyed on lockfile

- **GIVEN** two consecutive CI runs on the same branch with no `uv.lock` change
- **WHEN** the second run executes `uv sync`
- **THEN** `setup-uv` reports a cache hit on the wheel store

### Requirement: pre-commit runs in CI as a blocking gate

CI SHALL include a `pre-commit` job that runs `uv run pre-commit run --all-files`. The `quality`, `test`, `cov`, and `integration` jobs SHALL declare `needs: pre-commit` so they execute only on pre-commit success.

#### Scenario: pre-commit drift blocks the rest of CI

- **GIVEN** a PR that introduces a Ruff-style violation a local `pre-commit run` would catch
- **WHEN** the CI workflow starts
- **THEN** the `pre-commit` job fails with the same diagnostic
- **AND** `quality`, `test`, `cov`, and `integration` are reported as skipped (not run)

### Requirement: Codecov upload is optional and non-blocking

If a `CODECOV_TOKEN` secret is configured, the workflow SHALL upload coverage to Codecov. Absence of the token, or a Codecov upload failure, SHALL NOT fail the CI run.

#### Scenario: Missing Codecov token does not break CI

- **GIVEN** the repository has no `CODECOV_TOKEN` secret set
- **WHEN** the `cov` job runs
- **THEN** the workflow finishes green
- **AND** the Codecov step is reported as skipped

#### Scenario: Codecov upload failure does not break CI

- **GIVEN** `CODECOV_TOKEN` is set but the Codecov service returns 5xx
- **WHEN** the `cov` job runs
- **THEN** the Codecov step is reported as failed-with-warning
- **AND** the overall workflow run is still green (the step uses `continue-on-error: true`)

### Requirement: Makefile `.PHONY` enumerates every phony target

The `Makefile` `.PHONY` declaration SHALL include every target that is not a real file, including `outbox-retry-failed`.

#### Scenario: `outbox-retry-failed` works even if a file of that name exists

- **GIVEN** a stray `outbox-retry-failed` file accidentally lands in the repo root
- **WHEN** a contributor runs `make outbox-retry-failed`
- **THEN** the target still executes (because it is declared `.PHONY`)
