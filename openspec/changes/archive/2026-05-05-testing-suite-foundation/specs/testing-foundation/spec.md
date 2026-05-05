## ADDED Requirements

### Requirement: Pytest configuration

`pyproject.toml` MUST configure pytest with `testpaths = ["src"]`, `python_files = ["test_*.py"]`, `addopts = "-ra --strict-markers --strict-config"`, and the markers `unit`, `integration`, and `e2e`. Unmarked tests MUST default to `unit`.

#### Scenario: Strict markers
- **WHEN** a test file uses `@pytest.mark.foo` for an undefined marker
- **THEN** `pytest` exits non-zero before collecting

#### Scenario: Default discovery path
- **WHEN** a developer runs `pytest`
- **THEN** all tests under `src/**/tests/` are collected

### Requirement: Co-located test layout

Tests MUST live next to the code they exercise: `src/platform/tests/` for platform tests and `src/features/<F>/tests/` for each feature's tests. No top-level `tests/` directory MAY be created. Cross-feature shared fixtures MAY live only in `src/conftest.py`.

#### Scenario: Removing a feature removes its tests
- **WHEN** a developer deletes `src/features/kanban/`
- **THEN** all Kanban tests vanish in the same operation
- **AND** the rest of the test suite still collects without import errors

### Requirement: Test exclusion from distributable artifacts

The package builder configuration MUST exclude `**/tests/**` and `**/conftest.py` from the wheel and any sdist.

#### Scenario: Clean wheel
- **WHEN** `uv build` produces a wheel
- **THEN** unzipping the wheel reveals zero files matching `**/tests/**` or `**/conftest.py`

### Requirement: Coverage configuration

Coverage MUST be configured with `source = ["src"]` and `omit = ["src/**/tests/**", "src/conftest.py"]`. The minimum global coverage gate MUST be 70%, and a stricter gate of 85% MUST apply to `src/features/*/domain` and `src/features/*/application` directories.

#### Scenario: Coverage thresholds
- **WHEN** `make ci` runs and overall coverage drops below 70% or feature core drops below 85%
- **THEN** the run fails

### Requirement: Tests cannot leak across features

For every feature `F`, modules under `src/features/<F>/tests/` MUST NOT import from `src/features/<G>/` for any other feature `G`. Import-linter MUST enforce this.

#### Scenario: Cross-feature test import
- **WHEN** a Kanban test imports a future `users` feature module
- **THEN** `make lint-arch` fails

### Requirement: Make targets and CI integration

`Makefile` MUST expose `test`, `test-integration`, `test-e2e`, `test-feature FEATURE=<name>` targets. `make ci` MUST run quality + unit + integration + coverage. CI MUST include a job (or step) with Docker available that runs `make test-integration`.

#### Scenario: Local feature-scoped run
- **WHEN** a developer runs `make test-feature FEATURE=kanban`
- **THEN** only tests under `src/features/kanban/tests/` execute

#### Scenario: CI includes integration
- **WHEN** GitHub Actions runs the workflow
- **THEN** the integration job runs to completion using testcontainers Postgres
