# dev-makefile Specification

## Purpose

Document root `Makefile` targets for installing dependencies, running the API locally with reload, and running quality checks (lint, typecheck, tests) consistently for all contributors.

## Requirements

### Requirement: Makefile provides documented development targets

The system SHALL include a `Makefile` at the repository root that defines at least `help`, `sync`, `dev`, `lint`, `typecheck`, and `test` targets. The `help` target SHALL print a summary of available targets and what they do.

#### Scenario: Developer lists commands

- **WHEN** a developer runs `make help` or `make` with the default goal set to help
- **THEN** the output SHALL describe the available targets including sync, dev, lint, typecheck, and test

### Requirement: Sync target installs project dependencies

The system SHALL provide a `sync` target that synchronizes dependencies using the project lockfile (for example by running `uv sync`).

#### Scenario: Developer installs dependencies

- **WHEN** a developer runs `make sync`
- **THEN** the command SHALL complete using the project’s uv-managed environment without requiring manual `pip install` of individual packages for normal setup

### Requirement: Dev target runs the API locally with reload

The system SHALL provide a `dev` target that starts the FastAPI application with auto-reload suitable for local development (for example Uvicorn with `--reload` on the `main:app` application).

#### Scenario: Developer starts the server

- **WHEN** a developer runs `make dev` after dependencies are installed
- **THEN** the ASGI server SHALL start serving the application with reload enabled for code changes
