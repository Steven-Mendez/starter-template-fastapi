# Design: Fix Test Architecture Coupling

**Change ID**: `fix-test-architecture-coupling`

---

## Test Layer Dependency Rules

The test layer should follow the same hexagonal direction as the production code. Tests that exercise business behavior do so through the **application** layer. Tests that exercise persistence fidelity do so through **repository contracts**. Tests that exercise HTTP behavior do so through the **FastAPI client**.

```
tests/unit/domain/         → import from src.domain only
tests/unit/                → import from src.application + src.domain (via ports)
tests/integration/         → import from main, src.api, src.config
tests/support/             → import from src.application, src.domain (shared builders)
```

**Forbidden patterns in tests:**
- Import from `src.domain.kanban.repository` (after Change 1, this module won't exist)
- Calling repository business-operation methods directly to set up business test data
- Constructing `KanbanCommandHandlers` without `IdGenerator` and `Clock`
- Expecting a bare domain/contract type from a method that returns `AppResult`

---

## Revised `tests/support/kanban_builders.py`

### `KanbanBuilderRepository` — use new port surface

```python
class KanbanBuilderRepository(Protocol):
    def save(self, board: Board) -> Result[None, KanbanError]: ...
    def find_by_id(self, board_id: str) -> Result[Board, KanbanError]: ...
    def find_board_id_by_column(self, column_id: str) -> str | None: ...
```

`StoreBuilder` must be updated to use `save` and `find_by_id`:

```python
@dataclass(slots=True)
class StoreBuilder:
    repository: KanbanBuilderRepository

    def board(self, title: str = "Board") -> AppBoardSummary:
        board_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        board = Board(id=board_id, title=title, created_at=now, columns=[])
        expect_ok(self.repository.save(board))
        return AppBoardSummary(id=board_id, title=title, created_at=now)

    def _load_board(self, board_id: str) -> Board:
        return expect_ok(self.repository.find_by_id(board_id))
```

> **Note**: `StoreBuilder` still calls `uuid.uuid4()` directly because it is test support code, not production code. The constraint against direct UUID calls applies to `KanbanCommandHandlers` in production, not to test builders. Alternatively, `StoreBuilder` could accept an `IdGenerator` for determinism.

### `HandlerHarness.board()` — handle `AppResult`

```python
@dataclass(slots=True)
class HandlerHarness:
    commands: KanbanCommandHandlers
    queries: KanbanQueryHandlers

    def board(self, title: str = "Board") -> AppBoardSummary:
        result = self.commands.handle_create_board(CreateBoardCommand(title=title))
        return _expect_app_ok(result)   # extracts from AppOk or raises
```

---

## Revised `tests/unit/conftest.py`

```python
from tests.support.fakes import FakeIdGenerator, FakeClock
from datetime import datetime, timezone

_FIXED_CLOCK = FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc))

@pytest.fixture
def handler_harness() -> HandlerHarness:
    repository = InMemoryKanbanRepository()
    return HandlerHarness(
        commands=KanbanCommandHandlers(
            uow=InMemoryUnitOfWork(repository),
            id_gen=FakeIdGenerator(),    # generates sequential fake UUIDs
            clock=_FIXED_CLOCK,
        ),
        queries=KanbanQueryHandlers(repository=repository, readiness=repository),
    )
```

`FakeIdGenerator` with no pre-loaded IDs should fall back to generating real UUIDs so existing tests don't need to predict IDs. Alternatively, generate sequential IDs of the form `"00000000-0000-4000-8000-{counter:012}"`.

---

## Fate of `test_kanban_store.py`

The file contains 15+ test functions. Audit:

| Test | Correct level | Action |
|---|---|---|
| `test_list_boards_includes_newly_created_board` | Repository contract | Move to `test_kanban_repository_contract.py` if not already covered |
| `test_find_board_returns_err_when_id_unknown` | Repository contract | Already in contract test — **delete** |
| `test_board_title_can_be_changed_and_board_can_be_removed` | Command handler | Move to `test_kanban_command_handlers.py` |
| `test_removing_board_removes_nested_columns_and_cards` | Repository contract (cascade) | Move to `test_kanban_repository_contract.py` |
| `test_board_detail_lists_columns_in_creation_order` | Repository contract | Move to `test_kanban_repository_contract.py` |
| `test_card_is_nested_under_column_in_board_detail` | Repository contract | Move to `test_kanban_repository_contract.py` |
| `test_create_column_fails_when_board_does_not_exist` | Command handler | Move to `test_kanban_command_handlers.py` |
| `test_create_card_fails_when_column_does_not_exist` | Command handler | Move to `test_kanban_command_handlers.py` |
| `test_removing_column_removes_attached_cards` | Repository contract (cascade) | Move to `test_kanban_repository_contract.py` |
| `test_deleting_middle_column_keeps_contiguous_positions` | Command handler behavior | Move to `test_kanban_command_handlers.py` |
| `test_create_card_default_and_explicit_priority` | Command handler | Already covered in handler tests — **delete** |
| `test_board_detail_includes_card_priority` | Repository contract | Move or delete if covered |
| `test_update_card_*` tests | Command handler | Move to `test_kanban_command_handlers.py` |
| `test_card_title_can_update_*` | Command handler | Move to `test_kanban_command_handlers.py` |

After migration, `test_kanban_store.py` should be **deleted**. The remaining needed tests will live in the correct location.

---

## What Belongs in Each Test File (Post-Change)

| File | What it tests |
|---|---|
| `tests/unit/domain/test_board_domain.py` | Domain entity methods in isolation |
| `tests/unit/domain/test_column_domain.py` | Domain entity methods in isolation |
| `tests/unit/test_kanban_command_handlers.py` | Application command handlers with in-memory adapters |
| `tests/unit/test_kanban_repository_contract.py` | Both adapters satisfy the repository port contract |
| `tests/integration/test_kanban_api.py` | HTTP endpoints through `TestClient` |

---

## Master Migration Sequencing

> **Critical**: Several test fixes must be co-applied in the SAME commit as the architectural change they depend on. Applying an architectural change without its paired test fixes breaks the CI pipeline immediately.

| Step | Changes to co-apply in same PR | Rationale |
|---|---|---|
| **PR 1** | `relocate-ports-to-application-layer` + Phase 1 of `fix-test-architecture-coupling` tasks | All 4 test files with domain port imports break the moment the domain `repository/` directory is deleted. They must be updated atomically. |
| **PR 2** | `aggregate-repository-and-infrastructure-ports` + Phases 2–3 of `fix-test-architecture-coupling` | `KanbanCommandHandlers` constructor signature changes (adds `id_gen`, `clock`). The `handler_harness` fixture and `KanbanBuilderRepository` protocol must update in the same commit. |
| **PR 3** | `normalize-command-handler-contracts` + Phase 4 of `fix-test-architecture-coupling` | `handle_create_board` return type changes. `HandlerHarness.board()` must be updated in the same commit. |
| **PR 4** | `relocate-boardsummary-read-model` + Phase 7 of `fix-test-architecture-coupling` | `BoardSummary` import removed from domain. Test files referencing it must update atomically. |
| **PR 5** | `migrate-problem-details-to-api-adapter` | Independent — no test breakage. Apply anytime. |
| **PR 6** | `fix-patch-command-wire-concerns` | Independent — schema/command changes with accompanying test updates. Apply anytime. |
| **PR 7** | `domain-entity-unit-tests` | Purely additive. Apply anytime. |
| **PR 8** | `specification-pattern-integration` | Domain-only change. Apply anytime. |
| **PR 9** | `infrastructure-mapper-module` | Apply after PR 2 (since `save` replaces `save_board`). |
| **PR 10** | Remaining `fix-test-architecture-coupling` tasks (audit + delete `test_kanban_store.py`, delete `services/`) | Apply last, after all interface changes are settled. |

### Co-application rule for PR 1

In the same git commit:
1. Create `src/application/ports/` with port Protocol files.
2. Delete `src/domain/kanban/repository/`.
3. Update `tests/conftest.py`, `tests/unit/conftest.py`, `tests/unit/test_kanban_store.py`, `tests/unit/test_hexagonal_boundaries.py` import paths.
4. Update all production import sites.

Do NOT split into two commits where step 1–2 precede step 3–4. The CI pipeline runs `pytest` on every commit.

### Co-application rule for PR 2

In the same git commit:
1. Refactor `KanbanCommandHandlers` to accept `id_gen` and `clock`.
2. Update `handler_harness` fixture to pass `FakeIdGenerator()` and `FakeClock(...)`.
3. Update `KanbanBuilderRepository` protocol to use new method names.
4. Update `StoreBuilder` methods.

Do NOT separate handler changes from fixture changes.
