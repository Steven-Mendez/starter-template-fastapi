## Why

The template has zero tests today: no `tests/` directory, no pytest dependency, no fixtures, no CI test job. The hexagonal-architecture and python-testing-patterns skills both require a full pyramid (domain unit, use case unit with fakes, adapter integration with real infrastructure, contract suites shared across implementations, e2e through HTTP). Because this template will be cloned to start new services, future users need a turnkey testing setup that demonstrates how to test each layer correctly. Tests are co-located inside the feature ("delete the feature folder, delete its tests"), the convention that future features will copy from Kanban.

## What Changes

- Add development dependencies: `pytest`, `pytest-cov`, `pytest-asyncio`, `httpx`, `freezegun`, `polyfactory`, `testcontainers[postgresql]`.
- Configure pytest in `pyproject.toml` with `testpaths = ["src"]`, custom markers (`unit`, `integration`, `e2e`), and `--strict-markers`.
- Configure coverage with `omit = ["src/**/tests/**"]`.
- Co-locate tests under `src/<package>/tests/` for both `src/platform/tests/` and `src/features/kanban/tests/{fakes,contracts,unit,integration,e2e}`.
- Provide reusable in-memory fakes for every Kanban outbound port plus a `RecordingUoW` for commit/rollback assertions and a `FakeAppContainer` for HTTP override.
- Provide port contract test suites (parameterized) reused by both the in-memory fakes and the real SQLModel/Postgres adapter.
- Cover the Kanban domain (Board, Column, Card, ValidCardMoveSpecification), every use case via fakes, the HTTP adapter via `TestClient` + `app.dependency_overrides`, the persistence adapter via testcontainers Postgres, and the platform-level Problem+JSON / middleware behavior.
- Wire pytest into `Makefile` (`test`, `test-integration`, `test-e2e`, `test-feature FEATURE=<name>`) and into CI (`make ci` runs unit + integration with a Docker-enabled job).
- Enforce coverage gates: `>=85%` on `src/features/*/domain` and `src/features/*/application`, `>=70%` global.
- Exclude tests from any built wheel via the package builder configuration.
- Extend import-linter with a contract that prevents tests from leaking across features.

## Capabilities

### New Capabilities
- `testing-foundation`: Test runner configuration (pytest options, markers, coverage gates), the test layout convention (co-located, mirrored per feature/platform), and the rule that tests are excluded from distributable wheels.
- `kanban-tests`: The full set of test suites for the Kanban feature: domain, use cases (fakes), HTTP adapter (TestClient), persistence adapter (testcontainers), e2e flows, and the reusable contract suites.
- `platform-tests`: Tests for shared platform behavior: Problem+JSON shape (RFC 9457), request id middleware, app lifespan, settings.
- `ci-quality-gates`: CI workflow that runs the quality gate plus unit, integration (Docker-enabled), and coverage; Make targets that mirror the CI commands locally.

### Modified Capabilities
<!-- None at archive time of refactor-to-feature-first; this change introduces the first testing capabilities. -->

## Impact

- **Filesystem**: New test files under `src/platform/tests/` and `src/features/kanban/tests/`. New `conftest.py` at `src/conftest.py` for cross-feature fixtures (app factory, settings).
- **Configuration**: `pyproject.toml` gains `[tool.pytest.ini_options]`, `[tool.coverage.*]`, dev deps, and a build-system exclude block. `pyproject.toml` `[tool.importlinter]` gains a tests-isolation contract per feature.
- **Tooling**: `Makefile` gets `test`, `test-integration`, `test-e2e`, `test-feature` targets and `ci` is extended.
- **CI**: `.github/workflows/ci.yml` gains a job (or step) that has Docker available and runs `make test-integration`.
- **Dependencies**: Pure additive; no existing dependency is bumped.
- **Behavior**: No runtime API change.
- **Sequencing**: Depends on `refactor-to-feature-first` having been archived (paths under `src/features/kanban/...` and `src/platform/...` must already exist).
