# Spec: Test Architecture Boundaries

**Capability**: test-boundaries
**Change**: fix-test-architecture-coupling

---

## ADDED Requirements

### Requirement: TB-01 — Test files do not import port protocols from the domain layer


**Priority**: High

No file under `tests/` may import port Protocol classes from `src.domain`. After `relocate-ports-to-application-layer`, ports live in `src.application.ports`. Test files MUST reflect this.

**Acceptance Criteria**:
1. `rg "from src\.domain\.kanban\.repository" tests/` produces zero results.
2. All port protocol imports in test files resolve to `src.application.ports.*`.
3. `tests/unit/test_hexagonal_boundaries.py` imports port protocols from `src.application.ports`.
4. `tests/conftest.py` and `tests/unit/conftest.py` `kanban_store` fixture annotated with port from `src.application.ports`.

#### Scenario: Architecture boundary test imports from application ports

- Given: `test_hexagonal_boundaries.py` source file
- When: its import statements are inspected
- Then: no import from `src.domain.kanban.repository` appears
- And: port protocols are imported from `src.application.ports`

### Requirement: TB-06 — `src/domain/kanban/services/` directory does not exist

The system MUST satisfy this requirement as specified below.


**Priority**: Low

An empty module placeholder with no content creates false signals about the domain model. If domain services are needed in the future, they should be introduced with actual code.

**Acceptance Criteria**:
1. `src/domain/kanban/services/` directory does not exist.
2. No production code imports from `src.domain.kanban.services`.
3. The removal is confirmed by `rg "src\.domain\.kanban\.services" src/` producing zero results.

#### Scenario: Dead module is absent

- Given: the project source tree
- When: `src/domain/kanban/services/` is inspected
- Then: the directory does not exist

## ADDED Requirements

### Requirement: TB-02 — `handler_harness` fixture provides `IdGenerator` and `Clock` to command handlers


**Priority**: High

After `aggregate-repository-and-infrastructure-ports`, `KanbanCommandHandlers` requires `id_gen: IdGenerator` and `clock: Clock`. The `handler_harness` fixture MUST supply fake implementations.

**Acceptance Criteria**:
1. `tests/unit/conftest.py` imports `FakeIdGenerator` and `FakeClock` from `tests.support.fakes`.
2. `KanbanCommandHandlers(uow=..., id_gen=FakeIdGenerator(), clock=FakeClock(...))` is the construction form.
3. All existing tests using `handler_harness` pass without modification to test bodies.

#### Scenario: Handler harness creates entities with deterministic IDs in tests

- Given: `handler_harness` is constructed with `FakeIdGenerator()`
- When: `handler_harness.board("Test")` is called
- Then: the returned board has a non-empty, consistent `id`

### Requirement: TB-03 — `HandlerHarness.board()` handles `AppResult` return type


**Priority**: High

After `normalize-command-handler-contracts`, `handle_create_board` returns `AppResult[AppBoardSummary, ApplicationError]`. `HandlerHarness.board()` MUST extract the value from `AppOk` before returning.

**Acceptance Criteria**:
1. `HandlerHarness.board()` calls `_expect_app_ok(result)` or equivalent before returning.
2. `HandlerHarness.board()` raises `AssertionError` if `handle_create_board` returns `AppErr`.
3. All tests using `handler_harness.board(...)` continue to return `AppBoardSummary` without change to test code.

#### Scenario: HandlerHarness raises on unexpected error

- Given: `handler_harness` wired with a repository that fails on `save`
- When: `handler_harness.board("Test")` is called
- Then: `AssertionError` is raised with the error code, not a `TypeError`

### Requirement: TB-04 — `KanbanBuilderRepository` protocol matches the updated command repository port surface


**Priority**: High

`KanbanBuilderRepository` in `tests/support/kanban_builders.py` MUST mirror the updated `KanbanCommandRepositoryPort` method names.

**Acceptance Criteria**:
1. `KanbanBuilderRepository` contains `save`, `find_by_id`, and `find_board_id_by_column`.
2. `KanbanBuilderRepository` does not contain `create_board`, `get_board`, or `save_board`.
3. `StoreBuilder` methods only call `save` and `find_by_id` on the repository.
4. `InMemoryKanbanRepository` satisfies `KanbanBuilderRepository` (structural check).

#### Scenario: `StoreBuilder` creates board via `save`

- Given: a `StoreBuilder` backed by `InMemoryKanbanRepository`
- When: `store_builder.board("Sprint")` is called
- Then: the repository contains a board with `title == "Sprint"`
- And: `find_by_id(board.id)` returns `Ok(board)`

## ADDED Requirements

### Requirement: TB-05 — `test_kanban_store.py` does not contain helper functions that duplicate command handlers


**Priority**: High

`test_kanban_store.py` MUST not contain `_create_column_result`, `_create_card_result`, `_delete_column_result`, `_update_card`, or equivalent helpers. These behaviors are tested via command handlers or repository contracts.

**Acceptance Criteria**:
1. `test_kanban_store.py` does not exist, OR contains no private helper functions that orchestrate multiple repository calls to simulate business operations.
2. All business-behavior assertions previously in `test_kanban_store.py` are covered in `test_kanban_command_handlers.py`.
3. All persistence-fidelity assertions (cascade delete, ordering, field round-trips) are covered in `test_kanban_repository_contract.py`.

#### Scenario: Cascade delete is tested at the right level

- Given: `test_kanban_repository_contract.py` contains a test for cascade board deletion
- When: `remove(board_id)` is called on a board with columns and cards
- Then: `find_board_id_by_card(card_id)` returns `None` for all cards that were in the board
