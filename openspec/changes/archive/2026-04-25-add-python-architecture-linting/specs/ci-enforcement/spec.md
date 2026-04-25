# Spec: CI Architecture Enforcement

**Capability**: ci-enforcement
**Change**: add-python-architecture-linting

---

## ADDED Requirements

### Requirement: CI-01 — Architecture lint runs as a distinct CI step that blocks merging


**Priority**: High

`.github/workflows/ci.yml` MUST contain a dedicated `Architecture lint` step that executes `make lint-arch`. This step MUST run before `Typecheck` and fail the entire CI job on any contract violation.

**Acceptance Criteria**:
1. `.github/workflows/ci.yml` contains a step named `Architecture lint` or `architecture-lint`.
2. The step runs `make lint-arch` (or equivalent `uv run lint-imports`).
3. The step is placed after `Lint` and before or alongside `Typecheck`.
4. A PR introducing a domain-to-infrastructure import is blocked from merging because this CI step fails.
5. The step produces output naming the offending module and violated contract when it fails.

#### Scenario: CI blocks PR with architecture violation

- Given: a pull request that adds `from sqlalchemy import select` to `src/domain/kanban/models/board.py`
- When: the CI pipeline runs for that PR
- Then: the `Architecture lint` step exits non-zero
- And: the CI job status is `failed`
- And: the violation message appears in the CI step output
- And: the PR cannot be merged while the check is failing

#### Scenario: CI passes on clean PR

- Given: a pull request that only changes test files or adds a new domain entity with no forbidden imports
- When: the CI pipeline runs
- Then: the `Architecture lint` step exits 0 with status `KEPT` for all contracts
- And: the CI job continues to `Typecheck` and `Test`

### Requirement: CI-02 — Pre-commit hook runs architecture lint on every Python file commit


**Priority**: Medium

The `.pre-commit-config.yaml` MUST include an `architecture-lint` hook that runs `uv run lint-imports` when Python files are staged. This provides fast local feedback before code reaches CI.

**Acceptance Criteria**:
1. `.pre-commit-config.yaml` contains a hook with `id: architecture-lint`.
2. The hook entry is `uv run lint-imports` with `pass_filenames: false`.
3. The hook triggers on changes to files of type `python`.
4. `make precommit-run` executes the hook and exits 0 on clean code.
5. `make precommit-run` fails and names the violated contract when a forbidden import is introduced.

#### Scenario: Pre-commit hook fires on staged Python change

- Given: `src/application/commands/handlers.py` is modified to add `import fastapi`
- When: `git add src/application/commands/handlers.py && git commit -m "test"`
- Then: the `architecture-lint` pre-commit hook runs
- And: the hook exits non-zero
- And: the commit is rejected
- And: the output names the violated contract

### Requirement: CI-03 — Architecture lint failure message is actionable


**Priority**: Medium

When Import Linter detects a violation, the output MUST identify: the contract name, the source module, the target (forbidden) module, and enough context for the developer to locate and fix the violation.

**Acceptance Criteria**:
1. Violation output contains the contract `name` field value.
2. Violation output contains the fully-qualified module path of the source module (e.g., `src.domain.kanban.models.board`).
3. Violation output contains the forbidden import (e.g., `sqlalchemy` or `src.infrastructure.persistence.sqlmodel_repository`).
4. No violation output contains the word "Unknown" or omits the contract name.

#### Scenario: Violation message names source, target, and rule

- Given: `src/domain/kanban/models/board.py` contains `import sqlalchemy`
- When: `uv run lint-imports` runs
- Then: the output contains a line referencing `src.domain.kanban.models.board`
- And: the output contains `sqlalchemy`
- And: the output contains `Domain layer: no outward or framework dependencies` (the contract name)

### Requirement: CI-04 — Architecture lint is part of `make check` and `make precommit-run`


**Priority**: Medium

The architecture lint MUST be integrated into the developer workflow via the existing `make check` target so that running a single command covers style lint, architecture lint, and type checking.

**Acceptance Criteria**:
1. `make check` runs: `lint` → `lint-arch` → `typecheck` (in any order among these three).
2. `make check` exits non-zero if `lint-arch` fails.
3. `make precommit-run` runs the `architecture-lint` pre-commit hook as part of the full hook chain.
4. `make help` shows `lint-arch` with a description.

#### Scenario: `make check` includes architecture lint

- Given: `src/infrastructure/persistence/sqlmodel_repository.py` imports `from src.api.dependencies import get_app_container`
- When: `make check` is run
- Then: the `lint-arch` stage fails
- And: `make check` exits non-zero
- And: the violation is reported before mypy runs
