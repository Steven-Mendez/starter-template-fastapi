## 1. TDD Baseline for Tooling

- [x] 1.1 Add or update tests that fail when required pytest markers are missing or misconfigured.
- [x] 1.2 Add a failing validation check for expected `Makefile` targets (`lint`, `typecheck`, `test`) in documentation/help output.

## 2. Implement Local Quality Commands

- [x] 2.1 Update `Makefile` to implement `lint`, `typecheck`, and `test` targets and make help output include them.
- [x] 2.2 Configure Ruff and mypy in `pyproject.toml` and move test/tooling dependencies to development-only groups.
- [x] 2.3 Make tests from section 1 pass and ensure existing tests remain green.

## 3. CI Quality Gates

- [x] 3.1 Add a failing CI workflow test/check expectation (for example, required workflow presence and key jobs).
- [x] 3.2 Implement GitHub Actions workflow for lint, typecheck, and `pytest -m "not e2e"`.
- [x] 3.3 Verify the workflow and local commands align (same commands, same exit behavior).
