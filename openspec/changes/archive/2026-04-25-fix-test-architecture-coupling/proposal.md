# Proposal: Fix Test Architecture Coupling

**Change ID**: `fix-test-architecture-coupling`
**Priority**: High
**Status**: Proposed
**Depends on**: `relocate-ports-to-application-layer`, `aggregate-repository-and-infrastructure-ports`, `normalize-command-handler-contracts`

---

## Problem Statement

The test layer contains several systemic architectural violations that will cause test breakage after changes 1, 2, and 6 are applied — and that already represent architectural problems independent of those changes.

### Problem A: Test support code imports domain-resident ports

Five files import `KanbanRepositoryPort` or sub-protocols from `src.domain.kanban.repository`:

```
tests/conftest.py           line 9:  from src.domain.kanban.repository import KanbanRepositoryPort
tests/unit/conftest.py      line 11: from src.domain.kanban.repository import KanbanRepositoryPort
tests/unit/test_kanban_store.py line 10: from src.domain.kanban.repository import KanbanRepositoryPort as KanbanStore
tests/unit/test_hexagonal_boundaries.py lines 18-20: imports all three port protocols from domain
```

After `relocate-ports-to-application-layer` (Change 1), all four files will fail to import.

### Problem B: `test_kanban_store.py` duplicates command handler behavior at the repository level

`test_kanban_store.py` defines private helpers that reimplement the application command handlers:

| Helper in `test_kanban_store.py` | Duplicates |
|---|---|
| `_create_column_result` | `handle_create_column` |
| `_create_card_result` | `handle_create_card` |
| `_delete_column_result` | `handle_delete_column` |
| `_update_card` | `handle_patch_card` |

The tests then call repository business-operation methods (`update_board`, `delete_board`) directly. After `aggregate-repository-and-infrastructure-ports` (Change 2), these methods will no longer exist on the port.

This test file is effectively testing command-handler-level logic by bypassing the command handlers. The correct level of abstraction for these tests is `KanbanCommandHandlers` with in-memory adapters — not direct repository calls.

### Problem C: `tests/support/kanban_builders.py` `KanbanBuilderRepository` uses stale port surface

```python
class KanbanBuilderRepository(Protocol):
    def create_board(self, title: str) -> BoardSummary: ...   # ← will be removed
    def get_board(self, board_id: str) -> Result[Board, KanbanError]: ...  # ← renamed find_by_id
    def save_board(self, board: Board) -> Result[None, KanbanError]: ...   # ← renamed save
    def find_board_id_by_column(self, column_id: str) -> str | None: ...
```

`StoreBuilder` uses this protocol to bypass the application layer and manipulate repository state directly in tests. After Change 2, the protocol methods won't exist.

### Problem D: `HandlerHarness.board()` expects a bare `AppBoardSummary` return

```python
def board(self, title: str = "Board") -> AppBoardSummary:
    return self.commands.handle_create_board(CreateBoardCommand(title=title))
```

After `normalize-command-handler-contracts` (Change 6), `handle_create_board` returns `AppResult[AppBoardSummary, ApplicationError]`, not `AppBoardSummary` directly. All uses of `handler_harness.board(...)` in tests will break.

### Problem E: `tests/unit/conftest.py` instantiates concrete handler class directly

```python
KanbanCommandHandlers(uow=InMemoryUnitOfWork(repository))
```

After `aggregate-repository-and-infrastructure-ports` (Change 2), `KanbanCommandHandlers` requires `id_gen` and `clock` arguments. This fixture will fail to construct.

### Problem F: `src/domain/kanban/services/` is an empty dead directory

`src/domain/kanban/services/__init__.py` exports an empty `__all__`. The directory exists as a placeholder for domain services that were never implemented. It creates the false impression that domain services are a distinct module without any content.

---

## Rationale

Tests must track the architecture they exercise. When ports move and interfaces change, the test support layer must change in sync. The current test support code is tightly coupled to the **current** (incorrect) port location and method names, and will silently block implementation of the critical architecture changes.

Beyond breaking changes, `test_kanban_store.py` represents a deeper problem: it tests business behavior at the wrong layer. Testing business operations through a raw repository means that:
- Command handler bugs are not caught by these tests
- Repository tests cover more than they should (business decisions vs. persistence)
- Adding a new command handler won't be prompted by test coverage

Per `hex-design-guide.md` Section 15: "Unit tests for use cases: Use fake adapters. [...] Business rules belong mostly in domain and use-case tests."

---

## Scope

**In scope:**
- Update all import sites in `tests/` from `src.domain.kanban.repository` → `src.application.ports`.
- Rewrite `KanbanBuilderRepository` protocol to use new port method names (`save`, `find_by_id`, `remove`).
- Update `StoreBuilder` to use the new method names.
- Update `HandlerHarness.board()` to handle `AppResult` return.
- Update `tests/unit/conftest.py` `handler_harness` fixture to pass `FakeIdGenerator` and `FakeClock`.
- Delete or heavily rewrite `test_kanban_store.py`:
  - Delete all private helper functions that duplicate command handler behavior.
  - Move any tests that test business behavior (update, delete, move-card) to handler-level tests.
  - Retain only tests that verify repository-specific concerns (data persistence, query correctness, cascade deletes at the persistence level). These belong in `test_kanban_repository_contract.py`.
- Delete `src/domain/kanban/services/` directory (empty dead code).

**Out of scope:**
- Writing new business behavior tests (covered by `domain-entity-unit-tests` and existing handler tests).
- Changing `test_kanban_repository_contract.py` beyond import updates (its contract-testing approach is correct).

---

## Affected Modules

| File | Change |
|---|---|
| `tests/conftest.py` | Modified — import `KanbanRepositoryPort` from `src.application.ports` |
| `tests/unit/conftest.py` | Modified — import path update; add `FakeIdGenerator`, `FakeClock` to `handler_harness` |
| `tests/unit/test_hexagonal_boundaries.py` | Modified — import port protocols from `src.application.ports` |
| `tests/unit/test_kanban_store.py` | Heavily rewritten or deleted |
| `tests/support/kanban_builders.py` | Modified — `KanbanBuilderRepository` + `StoreBuilder` + `HandlerHarness` |
| `tests/support/fakes.py` | Added — `FakeIdGenerator`, `FakeClock` (from Change 2) |
| `src/domain/kanban/services/__init__.py` | Deleted |
| `src/domain/kanban/services/` | Deleted |

---

## Acceptance Criteria

1. No import from `src.domain.kanban.repository` exists in any file under `tests/`.
2. `KanbanBuilderRepository` protocol methods match the updated `KanbanCommandRepositoryPort` surface (`save`, `find_by_id`, `remove`).
3. `HandlerHarness.board()` extracts the value from `AppResult` before returning `AppBoardSummary`.
4. `handler_harness` fixture in `tests/unit/conftest.py` passes `FakeIdGenerator` and `FakeClock`.
5. `test_kanban_store.py` contains no helper functions that duplicate command handler logic.
6. All existing tests that test business behavior are either retained in `test_kanban_command_handlers.py` or verified to be covered elsewhere.
7. `src/domain/kanban/services/` does not exist.
8. Full test suite passes after this change: `python -m pytest tests/ -x`.

---

## Migration Strategy

> **Important**: Parts of this change must be co-applied with the architectural changes they depend on — not after them. If `relocate-ports-to-application-layer` is committed without updating test imports in the same commit, the entire test suite fails immediately. See the "Master Migration Sequencing" section in `design.md`.

The full sequencing for this change's tasks:

1. Apply `relocate-ports-to-application-layer` → update `tests/conftest.py`, `tests/unit/conftest.py` imports.
2. Apply `aggregate-repository-and-infrastructure-ports` → update `KanbanBuilderRepository`, `StoreBuilder`, handler fixture wiring.
3. Apply `normalize-command-handler-contracts` → update `HandlerHarness.board()`.
4. Audit `test_kanban_store.py` — for each test:
   - If it tests business behavior (update title, delete board, create columns): move to `test_kanban_command_handlers.py` if not already covered.
   - If it tests persistence concerns (data survives across repository instances, cascade deletes): move to `test_kanban_repository_contract.py`.
   - Delete the duplicative helpers.
5. Delete `src/domain/kanban/services/`.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| Business-behavior tests in `test_kanban_store.py` may not have equivalents in handler tests | Audit each test case and add missing coverage to `test_kanban_command_handlers.py` before deleting. |
| `StoreBuilder` is used in integration tests as well as unit tests | After refactor, `StoreBuilder` should use the new port surface. Integration tests using `ApiBuilder` don't depend on `StoreBuilder`. |
| Deleting empty `services/` directory changes the domain package surface | The directory exports nothing (`__all__ = []`). No code imports from it. Deletion is safe. |
