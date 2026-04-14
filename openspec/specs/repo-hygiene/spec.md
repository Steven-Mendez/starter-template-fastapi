# repo-hygiene Specification

## Purpose
TBD - created by archiving change improve-gitignore. Update Purpose after archive.
## Requirements
### Requirement: Root Git ignore policy for Python and tooling artifacts

The system SHALL include a `.gitignore` at the repository root that excludes Python bytecode and cache directories, virtual environment directories, distribution/build artifacts, common test and coverage outputs, and typical linter/type-checker cache directories.

#### Scenario: Developer runs tests and linters locally

- **WHEN** a developer runs Python, pytest, mypy, or ruff locally
- **THEN** generated cache and coverage files under those tools’ default paths SHALL be ignored by Git when listed in the status

### Requirement: Secrets and local environment files stay untracked

The system SHALL ignore `.env` and `.env.*` files while allowing an optional committed template `!.env.example` if present.

#### Scenario: Developer adds API keys to .env

- **WHEN** a developer creates a `.env` file with secrets
- **THEN** Git SHALL not track that file by default per ignore rules

### Requirement: Reproducible dependency lock remains tracked

The `.gitignore` SHALL NOT exclude `uv.lock` or `.python-version` so the project pin and lockfile remain committable.

#### Scenario: Team commits lockfile

- **WHEN** a maintainer stages `uv.lock` after `uv lock`
- **THEN** Git SHALL accept the file (it is not matched by ignore patterns)
