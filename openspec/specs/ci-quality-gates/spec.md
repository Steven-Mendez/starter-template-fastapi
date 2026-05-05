# ci-quality-gates Specification

## Purpose
TBD - created by archiving change testing-suite-foundation. Update Purpose after archive.
## Requirements
### Requirement: Make test targets

`Makefile` MUST expose:

- `test`: runs `pytest -m "not integration and not e2e"` with coverage measurement.
- `test-integration`: runs `pytest -m integration`.
- `test-e2e`: runs `pytest -m e2e`.
- `test-feature FEATURE=<name>`: runs `pytest src/features/$(FEATURE)/tests`.
- `cov`: prints a coverage report from the last test run with `--cov-report=term-missing`.

#### Scenario: Run unit tests only
- **WHEN** a developer runs `make test`
- **THEN** integration and e2e tests are skipped and unit tests pass with coverage above the configured gates

### Requirement: CI quality gate extended

`.github/workflows/ci.yml` MUST run, in this order: `make quality` (existing), `make test`, then `make test-integration` in a job/step where Docker is available. The workflow MUST fail if any of these fail. Coverage MUST be measured and the build MUST fail when coverage thresholds are breached.

#### Scenario: PR with failing integration test
- **WHEN** a pull request introduces a regression caught only by `make test-integration`
- **THEN** the GitHub Actions run reports a failed integration step and the PR cannot merge

#### Scenario: PR drops coverage
- **WHEN** a pull request lowers `src/features/kanban/application` coverage below 85%
- **THEN** the CI run fails

### Requirement: Pre-commit alignment

The pre-commit configuration MUST keep its existing hooks unchanged but MUST add a `pre-push` hook that runs `make test` so a regression at the unit level is caught before pushing. Integration tests MUST NOT run in pre-push (Docker latency).

#### Scenario: Pre-push runs unit tests
- **WHEN** a developer runs `git push`
- **THEN** the pre-push hook runs `make test` and blocks the push on failure
