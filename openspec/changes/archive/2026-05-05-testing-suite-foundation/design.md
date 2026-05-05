## Context

Following `refactor-to-feature-first`, the codebase is laid out as `src/platform/` + `src/features/<feature>/{domain,application,adapters,composition}`. Tests must demonstrate the canonical way to test each layer in this layout. The python-testing-patterns skill mandates fixtures, parameterization, mocking, exception assertions, freezegun for time, and proper test markers; the hexagonal-architecture skill adds contract suites at port level (run against multiple adapter implementations) and dependency-override patterns for the inbound HTTP adapter.

Constraints:

- mypy strict on tests too: `disallow_untyped_defs` includes test files (or, if too noisy, exclude only via `[[tool.mypy.overrides]]` for test modules — decision below).
- `make ci` must remain runnable on a vanilla GitHub Actions Ubuntu runner; integration tests rely on Docker which is available there but not always locally.
- No production code change; this is purely additive.

## Goals / Non-Goals

**Goals:**

- Co-located tests inside each feature, matching the "delete folder = delete feature + tests" property.
- One reusable contract suite per outbound port; run against the in-memory fake AND the SQLModel/Postgres adapter via parameterization.
- Demonstrate every test pattern relevant to the template: domain pure tests, use case tests with fakes, adapter integration with testcontainers, HTTP via `TestClient` with `app.dependency_overrides`, e2e via real Postgres, time freezing for clock-dependent code.
- Tests do not pollute the distributable wheel.
- Coverage gates publishable as `--cov-fail-under` so CI fails on regression.

**Non-Goals:**

- Property-based testing (Hypothesis): out of scope, can be added later.
- Async tests: production stack is sync; `pytest-asyncio` is added but unused for now (kept for future migration).
- Performance testing: out of scope.
- Mutation testing.
- A separate `tests/` root directory at repo level (rejected in favor of co-location).

## Decisions

### D1. Co-located test layout

Tests for a feature live under `src/features/<F>/tests/<area>/`. Tests for platform live under `src/platform/tests/`. Cross-feature fixtures live in `src/conftest.py`.

```text
src/
  conftest.py
  platform/tests/
    test_problem_details.py
    test_request_context_middleware.py
    test_app_lifespan.py
    test_settings.py
  features/kanban/tests/
    conftest.py
    fakes/
      __init__.py
      in_memory_repository.py        # impl. of KanbanCommandRepositoryPort + LookupPort
      in_memory_uow.py
      in_memory_query_repository.py
      fixed_clock.py
      sequential_id_generator.py
      recording_uow.py
      fake_app_container.py
    contracts/
      __init__.py
      kanban_repository_contract.py  # parameterizable suite
      query_repository_contract.py
      unit_of_work_contract.py
    unit/
      domain/
        test_board.py
        test_column.py
        test_card.py
        test_card_move_specification.py
      application/
        board/...
        card/...
        column/...
        health/test_check_readiness_use_case.py
      adapters/inbound/
        test_schemas_mappers.py
    integration/
      persistence/
        conftest.py                  # session-scoped Postgres testcontainer
        test_sqlmodel_uow_contract.py
        test_concurrency_constraints.py
        test_query_repository.py
    e2e/
      conftest.py                    # TestClient + dependency_overrides
      test_health.py
      test_boards_flow.py
      test_columns_flow.py
      test_cards_flow.py
      test_write_api_key_auth.py
      test_problem_details_shape.py
```

`pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["src"]
python_files = ["test_*.py"]
markers = [
  "unit: fast, no IO",
  "integration: requires docker / external services",
  "e2e: full flow through HTTP layer",
]
addopts = "-ra --strict-markers --strict-config"

[tool.coverage.run]
source = ["src"]
omit = ["src/**/tests/**", "src/conftest.py"]
```

### D2. Fakes implement ports faithfully

In-memory fakes implement the same outbound ports the production adapters do. They MUST satisfy the same contract suites. The `RecordingUoW` wraps `InMemoryUnitOfWork` to count `commit()`/`rollback()` calls and is used in use case tests that assert transactional behavior.

### D3. Contract suites parameterized once

Each outbound port contract suite is a module exposing parametrized `pytest.fixture` factories of the SUT. Unit tests parameterize against the in-memory fake; integration tests parameterize against the SQLModel adapter built on a session-scoped testcontainer. The same test functions run twice.

### D4. HTTP adapter tests use `app.dependency_overrides`

E2E HTTP tests build a real `app = create_app(test_settings)` and override `get_app_container` with a `FakeAppContainer` whose ports are in-memory fakes. This isolates the HTTP layer from persistence while still going through real FastAPI/Starlette plumbing including middleware and Problem+JSON. A subset of e2e tests (one happy path per resource) runs against a real Postgres testcontainer to verify the wired-up flow.

### D5. Time, IDs and randomness

Use `freezegun` for tests that depend on `ClockPort.now()`. Use a `SequentialIdGenerator` (not `uuid4`) in fakes so assertions are deterministic. Production code never sees these fakes.

### D6. Coverage gates and exclusions

- Module-scoped fail-under for `src/features/*/domain` and `src/features/*/application`: `>=85%`.
- Global fail-under: `>=70%`.
- `src/**/tests/**` and `src/conftest.py` excluded from coverage source.

### D7. Wheel exclusion

Add a builder section to exclude tests from the distributable artifact:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src"]
exclude = ["**/tests/**", "**/conftest.py"]
```

(If the project uses setuptools, equivalent `[tool.setuptools.packages.find] exclude = ["**.tests*"]`.)

### D8. CI: two jobs (fast / integration)

`.github/workflows/ci.yml` keeps the existing `quality` job and adds a second `integration` job that depends on `quality`. The integration job runs on `ubuntu-latest` (Docker available) and executes `make test test-integration`. The fast job runs only `make test` (no Docker needed). Make targets:

- `make test` → `pytest -m "not integration and not e2e"`
- `make test-integration` → `pytest -m integration`
- `make test-e2e` → `pytest -m e2e`
- `make test-feature FEATURE=<name>` → `pytest src/features/$(FEATURE)/tests`
- `make ci` → `quality + test + test-integration + cov`

### D9. Tests-isolation import-linter contract

For each feature, add a contract that forbids tests from importing other features:

```toml
[[tool.importlinter.contracts]]
name = "Kanban tests scope"
type = "forbidden"
source_modules = ["src.features.kanban.tests"]
forbidden_modules = []  # populated as features are added
```

## Risks / Trade-offs

- **[Risk] Testcontainers slow on cold runs** → Mitigation: session-scoped Postgres fixture; CI caches the Docker layer if the runner allows it.
- **[Risk] Co-located tests confuse some IDEs and packaging tools** → Mitigation: explicit `testpaths` and wheel `exclude`; documented in `_template/README.md`.
- **[Risk] Contract suites force extra abstraction in fakes** → Accepted: the suites are the canonical way to verify both implementations behave identically.
- **[Risk] Coverage gates produce false failures during the initial migration** → Mitigation: enable gates only after the initial test set lands; in this change, the gates target only the directories with tests provided.
- **[Trade-off] mypy on tests** → Decision: enable strict mypy on tests; allow `from __future__ import annotations` and ignore `disallow_untyped_defs` only inside `**/tests/**` if it becomes a friction point.

## Migration Plan

1. Add dev deps and pytest/coverage configuration; confirm `pytest --collect-only` runs against an empty suite.
2. Add `src/conftest.py`, `src/features/kanban/tests/conftest.py`, fakes module.
3. Write Kanban domain unit tests.
4. Write Kanban use case unit tests (per use case) with fakes.
5. Define and run contract suites against fakes.
6. Add testcontainers integration suite; run contract suites against the SQLModel adapter.
7. Add HTTP/e2e tests with `TestClient` and `app.dependency_overrides`.
8. Add platform tests (Problem+JSON shape, middleware, lifespan, settings).
9. Wire Make targets and CI integration job; flip coverage gates on.
10. Add wheel exclude block; verify `uv build` produces a clean wheel.

Rollback: revert the merge commit; only additive changes (no production code touched).

## Open Questions

- Do we want `pytest-xdist` for parallelism out of the box? (Lean: no — keep deps small; add later if test runtime grows.)
- Do we want `dirty-equals` for fluent assertions? (Lean: no by default — pytest's plain asserts are enough for a starter.)
