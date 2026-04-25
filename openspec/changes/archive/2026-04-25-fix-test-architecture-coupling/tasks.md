# Tasks: Fix Test Architecture Coupling

**Change ID**: `fix-test-architecture-coupling`
**Must be applied after**: `relocate-ports-to-application-layer`, `aggregate-repository-and-infrastructure-ports`, `normalize-command-handler-contracts`

---

## Implementation Checklist

### Phase 1 — Update import sites (applies after Change 1)

- [ ] `tests/conftest.py` line 9: change `from src.domain.kanban.repository import KanbanRepositoryPort` → `from src.application.ports.kanban_repository import KanbanRepositoryPort`.
- [ ] `tests/unit/conftest.py` line 11: same update.
- [ ] `tests/unit/test_hexagonal_boundaries.py` lines 18-20: update all three port protocol imports to `src.application.ports.*`.
- [ ] `tests/unit/test_kanban_store.py` line 10: update `KanbanStore` alias import.
- [ ] Search `tests/` for `src.domain.kanban.repository` — confirm zero remaining occurrences.

### Phase 2 — Wire `FakeIdGenerator` and `FakeClock` into `handler_harness` (applies after Change 2)

- [ ] Confirm `tests/support/fakes.py` exists with `FakeIdGenerator` and `FakeClock` (created by Change 2's task list).
- [ ] In `tests/unit/conftest.py`, update `handler_harness` fixture:
  - Import `FakeIdGenerator` and `FakeClock` from `tests.support.fakes`.
  - Pass `id_gen=FakeIdGenerator()` and `clock=FakeClock(datetime(2024, 1, 1, tzinfo=timezone.utc))` to `KanbanCommandHandlers(...)`.
- [ ] Run `python -m pytest tests/unit/test_kanban_command_handlers.py -v` — all tests pass.

### Phase 3 — Update `KanbanBuilderRepository` and `StoreBuilder` (applies after Change 2)

- [ ] Update `KanbanBuilderRepository` protocol in `tests/support/kanban_builders.py`:
  - Remove `create_board`, `get_board`, `save_board` methods.
  - Add `save`, `find_by_id`.
  - Keep `find_board_id_by_column`.
- [ ] Update `StoreBuilder.board()` — construct `Board(id=str(uuid.uuid4()), ...)` and call `self.repository.save(board)`.
- [ ] Update `StoreBuilder._load_board()` — call `self.repository.find_by_id(board_id)`.
- [ ] Update `StoreBuilder.column()` and `StoreBuilder.card()` — use `find_by_id` instead of `get_board` and `save` instead of `save_board`.

### Phase 4 — Update `HandlerHarness.board()` (applies after Change 6)

- [ ] In `tests/support/kanban_builders.py`, change `HandlerHarness.board()` return pattern:
  - Before: `return self.commands.handle_create_board(...)`
  - After: `return _expect_app_ok(self.commands.handle_create_board(...))`

### Phase 5 — Audit and migrate `test_kanban_store.py`

- [ ] For each test in `test_kanban_store.py`, determine correct location (see design.md table).
- [ ] Add missing tests to `test_kanban_command_handlers.py`:
  - `test_board_title_can_be_changed_and_board_can_be_removed` → handler test equivalent.
  - `test_create_column_fails_when_board_does_not_exist` → verify coverage exists.
  - `test_create_card_fails_when_column_does_not_exist` → verify coverage exists.
  - `test_deleting_middle_column_keeps_contiguous_positions` → already in handler tests.
  - `test_update_card_changes_priority` → verify handler tests cover.
  - `test_card_title_can_update_without_touching_description` → verify handler tests cover.
  - `test_update_card_sets_and_clears_due_at` → verify handler tests cover.
  - `test_omit_due_at_on_update_preserves_value` → verify handler tests cover.
- [ ] Add missing tests to `test_kanban_repository_contract.py`:
  - `test_removing_board_removes_nested_columns_and_cards` (cascade delete).
  - `test_card_is_nested_under_column_in_board_detail` (fetch fidelity).
  - `test_board_detail_lists_columns_in_creation_order` (ordering fidelity).
  - `test_board_detail_includes_card_priority` (priority field persistence).
  - `test_board_detail_includes_due_at_on_cards` (due_at field persistence).
- [ ] Delete all private helper functions from `test_kanban_store.py`: `_create_column_result`, `_create_card_result`, `_delete_column_result`, `_update_card`, `_find_card`, `_require_card`, `_get_card_result`.
- [ ] Delete `test_kanban_store.py` after all tests are confirmed covered elsewhere.
- [ ] Run `python -m pytest tests/unit/ -v` — no lost coverage.

### Phase 6 — Remove empty dead directory

- [ ] Delete `src/domain/kanban/services/__init__.py`.
- [ ] Delete `src/domain/kanban/services/` directory.
- [ ] Search for any import of `src.domain.kanban.services` — expect zero results.

### Phase 7 — Final verification

- [ ] Run `rg "src\.domain\.kanban\.repository" tests/` — expect zero results.
- [ ] Run `python -m pytest tests/ -x` — all tests pass.
- [ ] Run `python -m pytest tests/unit/test_hexagonal_boundaries.py -v` — all architecture tests pass.
