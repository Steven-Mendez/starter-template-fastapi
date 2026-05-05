## 1. Dependencies and configuration

- [x] 1.1 Add dev deps: `pytest>=8.3`, `pytest-cov>=5.0`, `pytest-asyncio>=0.24`, `httpx>=0.27`, `freezegun>=1.5`, `polyfactory>=2.18`, `testcontainers[postgresql]>=4.8`
- [x] 1.2 Add `[tool.pytest.ini_options]` with `testpaths`, `python_files`, `markers`, `addopts`
- [x] 1.3 Add `[tool.coverage.run]` and `[tool.coverage.report]` with omits, `fail_under = 70`, and per-path stricter thresholds
- [x] 1.4 Add wheel exclude block for tests/conftest in `pyproject.toml`
- [x] 1.5 Add per-feature import-linter contract for `src.features.kanban.tests`

## 2. Fakes and shared fixtures

- [x] 2.1 Create `src/conftest.py` with the test app factory and a default `test_settings`
- [x] 2.2 Create `src/features/kanban/tests/__init__.py` and `src/features/kanban/tests/conftest.py`
- [x] 2.3 Implement `InMemoryKanbanRepository` (commands+lookup) under `tests/fakes/in_memory_repository.py`
- [x] 2.4 Implement `InMemoryUnitOfWork` and `RecordingUoW` under `tests/fakes/`
- [x] 2.5 Implement `InMemoryQueryRepository`, `FixedClock`, `SequentialIdGenerator`
- [x] 2.6 Implement `FakeAppContainer` consumed by e2e tests via `app.dependency_overrides`

## 3. Domain unit tests

- [x] 3.1 `test_board.py` covers add/delete/get column, find/get card, move within and across columns, error branches
- [x] 3.2 `test_column.py` covers insert_card / move_card_within / extract_card / position recalculation
- [x] 3.3 `test_card.py` covers `apply_patch` (each field, including `clear_due_at`)
- [x] 3.4 `test_card_move_specification.py` covers every branch of `ValidCardMoveSpecification`

## 4. Use case unit tests (with fakes + RecordingUoW)

- [x] 4.1 `application/board/test_create_board_use_case.py` (happy path, recorded commit)
- [x] 4.2 `application/board/test_patch_board_use_case.py` (rename, missing board, no-changes)
- [x] 4.3 `application/board/test_delete_board_use_case.py`
- [x] 4.4 `application/board/test_get_board_use_case.py`, `test_list_boards_use_case.py`
- [x] 4.5 `application/column/test_create_column_use_case.py`, `test_delete_column_use_case.py`
- [x] 4.6 `application/card/test_create_card_use_case.py` (column missing, board missing)
- [x] 4.7 `application/card/test_patch_card_use_case.py` (`PATCH_NO_CHANGES`, move + edit, `clear_due_at`)
- [x] 4.8 `application/card/test_get_card_use_case.py`
- [x] 4.9 `application/health/test_check_readiness_use_case.py`
- [x] 4.10 Verify rollback semantics by raising inside a fake repository call and asserting `RecordingUoW.rollback_count == 1`

## 5. Contract suites

- [x] 5.1 `contracts/kanban_repository_contract.py` — parameterized by SUT factory, exercises save/find_by_id/find_board_id_by_column/find_board_id_by_card and version increments
- [x] 5.2 `contracts/query_repository_contract.py` — exercises list/get with empty and populated state
- [x] 5.3 `contracts/unit_of_work_contract.py` — enter/exit, commit/rollback contract, expire_on_commit semantics
- [x] 5.4 Wire each suite into `unit/` (against fakes) and `integration/persistence/` (against SQLModel)

## 6. Persistence integration

- [x] 6.1 `integration/persistence/conftest.py` starts a session-scoped Postgres testcontainer and runs `alembic upgrade head` once
- [x] 6.2 `test_sqlmodel_uow_contract.py` parameterizes the contract suites with the SQLModel SUT
- [x] 6.3 `test_concurrency_constraints.py` verifies the constraint introduced by `20260427_0002_persistence_concurrency_constraints`
- [x] 6.4 `test_query_repository.py` verifies the read-side view returns identical projections to the in-memory query repository

## 7. HTTP / e2e

- [x] 7.1 `e2e/conftest.py` builds the app, applies `app.dependency_overrides[get_app_container] = FakeAppContainer(...)`, returns a `TestClient`
- [x] 7.2 `test_health.py` covers ready/degraded
- [x] 7.3 `test_boards_flow.py` covers create/list/get/patch/delete
- [x] 7.4 `test_columns_flow.py` covers create/delete + nested under boards
- [x] 7.5 `test_cards_flow.py` covers create/get/patch including move and `clear_due_at`
- [x] 7.6 `test_write_api_key_auth.py` covers 401 on writes when key missing/wrong, 200/201 when correct, no-op when key not configured
- [x] 7.7 `test_problem_details_shape.py` covers RFC 9457 fields and `request_id`/`code`
- [x] 7.8 At least one happy-path e2e test per resource MUST run with the testcontainer Postgres (full real flow)

## 8. Platform tests

- [x] 8.1 `platform/tests/test_problem_details.py` covers all five exception handlers
- [x] 8.2 `platform/tests/test_request_context_middleware.py` covers header echo, generation, and JSON log line
- [x] 8.3 `platform/tests/test_app_lifespan.py` covers single platform construction, register_kanban call, shutdown hook
- [x] 8.4 `platform/tests/test_settings.py` covers env parsing, list parsing, defaults, validation

## 9. Make + CI

- [x] 9.1 Update `Makefile`: add `test`, `test-integration`, `test-e2e`, `test-feature`, `cov`; extend `ci`
- [x] 9.2 Update `.github/workflows/ci.yml`: keep `quality` job; add a step (or job) running `make test` then `make test-integration` (Docker available on `ubuntu-latest`)
- [x] 9.3 Update `.pre-commit-config.yaml` to add a `pre-push` hook running `make test`
- [x] 9.4 Confirm CI passes end-to-end on a draft PR

## 10. Verification

- [x] 10.1 `make ci` green locally (with Docker available)
- [x] 10.2 Coverage gates: global `>=70%`, `src/features/kanban/{domain,application}` `>=85%`
- [x] 10.3 `uv build` produces a wheel with zero `tests/` or `conftest.py` entries
- [x] 10.4 `make test-feature FEATURE=kanban` collects only Kanban tests
- [x] 10.5 `make lint-arch` green (tests-isolation contract enforced)
