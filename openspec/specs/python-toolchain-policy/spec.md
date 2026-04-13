# python-toolchain-policy Specification

## Purpose

Define canonical configuration for lint and type-check tools and clear boundaries between runtime and developer-only dependencies so local runs match CI.

## Requirements

### Requirement: Tooling configuration SHALL be source-controlled

The system SHALL define linting and typing tool configuration in `pyproject.toml` so local and CI execution use the same rules.

#### Scenario: Developer runs lint locally

- **WHEN** a developer executes the lint command from the project root
- **THEN** Ruff SHALL load configuration from version-controlled project files
- **THEN** results SHALL be reproducible in CI

### Requirement: Runtime and developer dependencies SHALL be separated

The system SHALL keep production runtime dependencies distinct from development-only dependencies.

#### Scenario: Building production environment

- **WHEN** dependencies are installed for runtime-only execution
- **THEN** test runners and local-only quality tools SHALL not be required runtime dependencies
