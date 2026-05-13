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
