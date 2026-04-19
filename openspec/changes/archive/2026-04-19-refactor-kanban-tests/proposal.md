## Why

Kanban tests currently have duplicated setup patterns and brittle data construction, which increases maintenance cost and slows feature delivery. A focused refactor is needed to keep tests readable, deterministic, and easier to extend.

## What Changes

- Reorganize Kanban tests into clearer unit and API-focused sections with shared helpers.
- Introduce reusable fixtures/builders for board and card setup to remove repetitive test boilerplate.
- Standardize deterministic test data generation to avoid order-dependent and time-dependent failures.
- Preserve existing observable behavior coverage while improving test maintainability.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `ci-quality-gates`: Add deterministic and maintainable Kanban test-suite expectations under existing quality requirements.

## Impact

- Affected code: `tests/` (Kanban-focused test modules, fixtures, and test helpers).
- Affected quality gates: `pytest` in local and CI workflows.
- No API contract or runtime dependency changes expected.
