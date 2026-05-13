## ADDED Requirements

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
