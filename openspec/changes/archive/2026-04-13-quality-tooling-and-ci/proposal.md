## Why

The starter template lacks automated quality gates, so regressions can merge without immediate feedback. We need a reproducible baseline for linting, typing, and tests that runs both locally and in CI.

## What Changes

- Add a CI workflow that runs lint, type-checking, and tests on pull requests.
- Define Ruff and mypy configuration in `pyproject.toml` and expose dedicated `Makefile` targets.
- Separate production dependencies from developer-only tooling dependencies.
- Strengthen pytest marker conventions to support selective pipelines (`unit`, `integration`, `e2e`).

## Capabilities

### New Capabilities
- `ci-quality-gates`: Enforce repository quality checks in GitHub Actions before merge.
- `python-toolchain-policy`: Define canonical lint/type/test tooling behavior and dependency boundaries.

### Modified Capabilities
- `dev-makefile`: Extend the development command surface with lint/type/test targets and clear composition rules.

## Impact

- Affected files: `pyproject.toml`, `Makefile`, `.github/workflows/*`, `tests/*` marker configuration.
- New dependency group entries for tooling (Ruff, mypy, pytest plugins if needed).
- CI runtime increases slightly but provides earlier defect detection and clearer contributor feedback.
