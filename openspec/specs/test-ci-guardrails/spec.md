# test-ci-guardrails Specification

## Purpose
Define quality guardrails so CI enforces the non-e2e coverage gate and integration tests validate the real application composition path through app-factory and lifespan startup.

## Requirements

### Requirement: TCG-01 - CI quality pipeline MUST enforce non-e2e coverage gate

**Priority**: High

The CI quality workflow MUST execute the repository coverage-gated test command so pull requests fail when non-e2e coverage falls below the configured threshold.

**Acceptance Criteria**:
1. The quality workflow invokes `make test-cov` as its test command.
2. The workflow does not rely on a non-coverage test command for the quality test gate.
3. Repository tooling tests assert the CI workflow includes `make test-cov`.
4. If non-e2e coverage is below the configured threshold, CI quality fails.

#### Scenario: CI executes coverage-gated test target

- Given: a pull request triggers the CI quality workflow
- When: the quality test step runs
- Then: it executes `make test-cov`
- And: coverage threshold enforcement is active for the test gate

#### Scenario: Tooling test protects CI command regression

- Given: the workflow file content is validated by project tooling tests
- When: the workflow test inspects the quality pipeline commands
- Then: it asserts that `make test-cov` is present
- And: a regression to a non-coverage command causes the tooling test to fail

### Requirement: TCG-02 - Integration fixtures MUST boot app through composition root

**Priority**: High

Integration test fixtures MUST construct the ASGI app through the same app-factory plus lifespan path used in production composition, instead of mutating global app state or wiring the container manually.

**Acceptance Criteria**:
1. Integration fixtures create clients from `create_app(AppSettings(...))`.
2. Fixture startup relies on app lifespan initialization to wire the container.
3. Fixtures do not call manual global container mutation helpers for app setup.
4. Integration tests continue to pass with persistence and API-key settings provided through `AppSettings` inputs.

#### Scenario: Integration client boots through app factory and lifespan

- Given: an integration fixture needs an API client with PostgreSQL test settings
- When: it creates the app via `create_app(AppSettings(postgresql_dsn=...))` and opens `TestClient`
- Then: dependency container wiring is initialized by lifespan startup
- And: requests execute against the composed application state

#### Scenario: Write-key integration client uses composition inputs

- Given: an integration fixture needs a write-protected API client
- When: it passes `write_api_key` and database settings into `AppSettings` at app creation
- Then: request authorization behavior reflects that configured key
- And: no global app/container mutation is required for fixture setup
