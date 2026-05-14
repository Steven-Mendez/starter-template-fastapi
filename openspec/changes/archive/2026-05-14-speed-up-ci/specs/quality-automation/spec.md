## ADDED Requirements

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
