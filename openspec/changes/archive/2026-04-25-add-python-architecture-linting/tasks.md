# Tasks: Add Python Architecture Linting

**Change ID**: `add-python-architecture-linting`
**Must be applied after**: `relocate-ports-to-application-layer` (eliminates existing violations)

---

## Implementation Checklist

### Phase 1 — Add `import-linter` dependency

- [ ] Add `import-linter` to the `dev` dependency group in `pyproject.toml`:
  ```
  "import-linter>=2.1",
  ```
- [ ] Run `uv sync` to install and update `uv.lock`.
- [ ] Verify: `uv run lint-imports --version` exits 0.

### Phase 2 — Configure Import Linter contracts in `pyproject.toml`

Add the following section to `pyproject.toml` after `[tool.mypy]`:

- [ ] Add root configuration block:
  ```toml
  [tool.importlinter]
  root_packages = ["src"]
  include_external_packages = true
  ```

- [ ] Add Contract 1 — Domain isolation:
  ```toml
  # hex-design-guide.md §3, §16, §29 Rule 1
  [[tool.importlinter.contracts]]
  name = "Domain layer: no outward or framework dependencies"
  type = "forbidden"
  source_modules = ["src.domain"]
  forbidden_modules = [
      "src.application", "src.api", "src.infrastructure", "src.config",
      "fastapi", "starlette", "sqlmodel", "sqlalchemy",
      "uvicorn", "httpx", "alembic", "pydantic_settings", "psycopg",
  ]
  ```

- [ ] Add Contract 2 — Application isolation:
  ```toml
  # hex-design-guide.md §4, §16, §29 Rule 2
  # pydantic intentionally NOT forbidden — see hex-design-guide.md §35
  [[tool.importlinter.contracts]]
  name = "Application layer: no infrastructure or framework dependencies"
  type = "forbidden"
  source_modules = ["src.application"]
  forbidden_modules = [
      "src.api", "src.infrastructure", "src.config",
      "fastapi", "starlette", "sqlmodel", "sqlalchemy",
      "uvicorn", "httpx", "alembic", "pydantic_settings", "psycopg",
  ]
  ```

- [ ] Add Contract 3 — API adapter restrictions:
  ```toml
  # hex-design-guide.md §7, §8, §16
  [[tool.importlinter.contracts]]
  name = "API adapter: no infrastructure bypass or direct domain access"
  type = "forbidden"
  source_modules = ["src.api"]
  forbidden_modules = [
      "src.infrastructure", "src.domain",
      "sqlmodel", "sqlalchemy", "alembic", "uvicorn", "psycopg",
  ]
  ```

- [ ] Add Contract 4 — Infrastructure restrictions:
  ```toml
  # hex-design-guide.md §6, §16
  [[tool.importlinter.contracts]]
  name = "Infrastructure: no inbound adapter imports"
  type = "forbidden"
  source_modules = ["src.infrastructure"]
  forbidden_modules = ["src.api"]
  ```

- [ ] Add Contract 5 — Core inward layers:
  ```toml
  # hex-design-guide.md §1 "Dependencies point inward"
  [[tool.importlinter.contracts]]
  name = "Core inward dependency direction"
  type = "layers"
  layers = ["src.api", "src.application", "src.domain"]
  ```

- [ ] Run `uv run lint-imports` — confirm **all contracts pass** (zero violations).
  - If violations appear, verify `relocate-ports-to-application-layer` was applied first.
  - If violations remain after port relocation, add `ignore_imports` with a `# TODO: remove after <change-id>` comment and file a follow-up task.

### Phase 3 — Add `lint-arch` Make target

- [ ] In `Makefile`, add the `lint-arch` target:
  ```makefile
  lint-arch: ## Check Hexagonal Architecture import contracts (Import Linter)
      uv run lint-imports
  ```

- [ ] Update the `check` target to include `lint-arch`:
  ```makefile
  check: lint lint-arch typecheck ## Run lint + architecture lint + type checks
  ```

- [ ] Update the `.PHONY` list to include `lint-arch`.
- [ ] Verify: `make lint-arch` exits 0 on clean code.
- [ ] Verify: `make check` runs lint, lint-arch, and typecheck in sequence.

### Phase 4 — Add pre-commit hook

- [ ] In `.pre-commit-config.yaml`, add the architecture lint hook under the `local` repo section:
  ```yaml
  - id: architecture-lint
    name: architecture lint (import-linter)
    entry: uv run lint-imports
    language: system
    pass_filenames: false
    types: [python]
  ```

- [ ] Run `make precommit-run` to verify the hook runs without error.

### Phase 5 — Update CI workflow

- [ ] In `.github/workflows/ci.yml`, add the architecture lint step between `Lint` and `Typecheck`:
  ```yaml
  - name: Architecture lint
    run: make lint-arch
  ```

- [ ] Commit and push to a branch; verify the CI `Architecture lint` step appears and passes in GitHub Actions.

### Phase 6 — Enhance pytest boundary checker with external library check

- [ ] In `tests/unit/test_hexagonal_boundaries.py`, add the `EXTERNAL_LIBRARY_DENY` dict and `test_forbidden_external_library_imports` function (see design.md for the exact code).
- [ ] Run `python -m pytest tests/unit/test_hexagonal_boundaries.py::test_forbidden_external_library_imports -v` — confirm it passes on clean code.
- [ ] Manually add `import sqlalchemy` to `src/domain/kanban/models/card.py`, run the test — confirm it fails with a clear violation message.
- [ ] Revert the manual change.

### Phase 7 — Prove the linter catches violations (validation fixtures)

- [ ] Create a temporary file `src/domain/kanban/models/_violation_fixture.py` with:
  ```python
  import fastapi   # intentional violation for testing only
  ```
- [ ] Run `make lint-arch` — confirm it fails, naming `src.domain.kanban.models._violation_fixture` and the violated contract.
- [ ] Delete `_violation_fixture.py`.
- [ ] Create a temporary file `src/application/commands/_sql_violation.py` with:
  ```python
  from sqlmodel import Session  # intentional violation for testing only
  ```
- [ ] Run `make lint-arch` — confirm it fails for Contract 2.
- [ ] Delete `_sql_violation.py`.
- [ ] Confirm `make lint-arch` exits 0 after deletion.

### Phase 8 — Document the architecture contracts

- [ ] In `docs/architecture.md`, add an "Architecture Linting" section with:
  - Description of the two-tool approach (Import Linter + pytest checker).
  - The `make lint-arch` command.
  - How to add a new port without breaking contracts (from design.md).
  - How to add a new outbound adapter without breaking contracts (from design.md).
  - How to add a new inbound adapter (driver) without breaking contracts (from design.md).
  - Explanation of how to add a justified `ignore_imports` exception.

### Phase 9 — Final verification

- [ ] Run `make check` — all lint, architecture lint, and typecheck steps pass.
- [ ] Run `make test-fast` — all pytest tests pass including `test_hexagonal_architecture_boundaries` and `test_forbidden_external_library_imports`.
- [ ] Run `make precommit-run` — all pre-commit hooks pass.
- [ ] Confirm `uv.lock` is committed with the new `import-linter` entry.
