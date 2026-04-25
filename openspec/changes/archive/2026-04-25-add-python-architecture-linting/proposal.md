# Proposal: Add Python Architecture Linting

**Change ID**: `add-python-architecture-linting`
**Priority**: High
**Status**: Proposed
**Recommended apply order**: After `relocate-ports-to-application-layer` (eliminates the only existing violations before the linter runs)

---

## Problem Statement

The project has a sophisticated hand-written boundary checker in `tests/unit/test_hexagonal_boundaries.py` that enforces import direction using AST parsing. This is valuable, but has three structural weaknesses:

### Weakness 1: Architecture violations are only caught during `make test-fast`

The boundary checker runs as pytest. It is not part of `make lint`. A developer can `make check` (lint + typecheck) on every commit and never catch an architecture violation until tests run. The pipeline is:

```
make lint       ← ruff only (style, imports order, flake-style rules)
make typecheck  ← mypy only (type correctness)
make test-fast  ← pytest (business logic + boundary rules mixed together)
```

Architecture violations should be caught at lint time, before tests run.

### Weakness 2: The boundary checker is opaque and non-standard

The checker is ~500 lines of custom Python. Its contract definitions live in a dict literal (`DENY_MATRIX`) inside a test file. There is no architecture contract manifest readable by standard tooling, IDEs, or CI dashboards. A new engineer cannot see the contracts without reading implementation code.

### Weakness 3: No enforcement for forbidden external library imports

The existing checker tracks internal module imports (`src.*`). It does not detect when a domain or application module imports `fastapi`, `sqlmodel`, `sqlalchemy`, `sqlalchemy.ext.asyncio`, `starlette`, `uvicorn`, `httpx`, or `alembic`. These are equally forbidden per the hexagonal architecture rules (`hex-design-guide.md` Rule 1–2, Section 16) but are invisible to the current checker.

**Concrete example**: Nothing prevents a developer from adding `from sqlalchemy import select` to `src/domain/kanban/models/board.py`. The AST boundary checker would miss it because `sqlalchemy` is not in `src.*`.

---

## Rationale

Per `hex-design-guide.md` Section 29:
> Rule 1: Domain has no framework imports — `grep -R "fastapi" app/domain` → no results.
> Rule 2: Application has no database imports — `grep -R "sqlalchemy" app/application` → no results.

The guide explicitly calls these rules "a checklist" — implying they should be mechanically verified. Import Linter turns this checklist into a static contract enforced at lint time, before tests run, and before code is committed.

---

## Scope

**In scope:**
- Add `import-linter` as a dev dependency.
- Define Import Linter contracts in `pyproject.toml` covering all four hexagonal layers plus the config module.
- Add a `lint-arch` Make target that runs `lint-imports`.
- Update `check` Make target to include `lint-arch`.
- Add Import Linter to the `.pre-commit-config.yaml` hook chain.
- Add an architecture lint step to `.github/workflows/ci.yml`.
- Add documentation explaining how to add a new port or adapter without breaking the contracts.
- Enhance `tests/unit/test_hexagonal_boundaries.py` to cover rules Import Linter cannot enforce (not replacing it — both tools are complementary).

**Out of scope:**
- Replacing the existing pytest boundary checker (it covers structural rules Import Linter cannot: route handler injection patterns, adapter surface parity).
- Adding Grimp as a standalone tool (Import Linter uses Grimp internally; no additional value for enforcement).
- Adding Pylint or Flake8 plugins (Ruff + Import Linter + pytest checker fully cover the required rules).
- Changing production code to fix existing violations (apply `relocate-ports-to-application-layer` first).

---

## Affected Modules

| File | Change |
|---|---|
| `pyproject.toml` | Modified — add `import-linter` to dev dependencies; add `[tool.importlinter]` section |
| `Makefile` | Modified — add `lint-arch` target; add to `check` |
| `.pre-commit-config.yaml` | Modified — add Import Linter hook |
| `.github/workflows/ci.yml` | Modified — add `make lint-arch` step |
| `docs/architecture.md` | Modified — add "Adding a port or adapter" guide |
| `tests/unit/test_hexagonal_boundaries.py` | Modified — add external library forbidden import check |

---

## Acceptance Criteria

1. `make lint-arch` exits 0 when all import contracts are satisfied.
2. `make lint-arch` exits non-zero and names the offending module when a contract is violated.
3. Adding `import fastapi` to `src/domain/kanban/models/board.py` causes `make lint-arch` to fail.
4. Adding `import sqlmodel` to `src/application/commands/handlers.py` causes `make lint-arch` to fail.
5. `make check` includes `lint-arch` and fails on architecture violations.
6. `.github/workflows/ci.yml` runs `make lint-arch` as a distinct CI step that blocks merging.
7. The pre-commit hook runs `lint-imports` on every Python file commit.
8. All contracts are documented in `pyproject.toml` with a name and a `hex-design-guide.md` section reference in a comment.
9. All exceptions to contracts are explicit and include a comment explaining why they are allowed.
10. The pytest boundary checker (`test_hexagonal_architecture_boundaries`) continues to pass alongside Import Linter.

---

## Migration Strategy

1. Apply `relocate-ports-to-application-layer` first — this eliminates the only existing violation where `src.application.queries.handlers` and `src.application.shared.unit_of_work` import from `src.domain.kanban.repository` (a domain path that will no longer exist).
2. Add `import-linter` to dev dependencies and run `uv sync`.
3. Add Import Linter contracts to `pyproject.toml`.
4. Run `uv run lint-imports` and confirm zero violations.
5. Add Makefile target, pre-commit hook, and CI step.
6. Add external library forbidden import check to the pytest boundary checker.
7. Add documentation to `docs/architecture.md`.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Import Linter may produce false positives for legitimate cross-layer imports (e.g., infrastructure importing application contracts) | Configure contracts with correct `source_modules` scoping. Infrastructure can import application — only specific forbidden paths are blocked. |
| New contracts may conflict with existing pytest boundary tests | Both tools run independently. Conflicts in coverage are fine — redundancy is better than gaps. Contradictions (one passes, other fails for same module) would indicate a misconfiguration — validate both pass on clean code. |
| `src.config` is not a hexagonal layer but is imported by infrastructure | The `src.config` module is excluded from layer contracts; it is only forbidden in domain and application (matching the existing DENY_MATRIX). |
| Import Linter doesn't check dynamic imports (`importlib`) | Accepted — dynamic imports are rare in this codebase and would be caught by code review. |
