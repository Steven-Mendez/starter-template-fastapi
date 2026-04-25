# Tasks: Aggregate-Level Repository Interface and Infrastructure Ports

**Change ID**: `aggregate-repository-and-infrastructure-ports`
**Depends on**: `relocate-ports-to-application-layer` (must be complete first)

---

## Implementation Checklist

### Phase 1 — Add new port files

- [ ] Create `src/application/ports/id_generator.py` with `IdGenerator(Protocol)` defining `next_id() -> str`.
- [ ] Create `src/application/ports/clock.py` with `Clock(Protocol)` defining `now() -> datetime`.
- [ ] Update `src/application/ports/__init__.py` to re-export `IdGenerator` and `Clock`.

### Phase 2 — Add infrastructure adapters

- [ ] Create `src/infrastructure/adapters/__init__.py`.
- [ ] Create `src/infrastructure/adapters/uuid_id_generator.py` with `UUIDIdGenerator` implementing `IdGenerator`.
- [ ] Create `src/infrastructure/adapters/system_clock.py` with `SystemClock` implementing `Clock`.

### Phase 3 — Update `KanbanCommandRepositoryPort`

- [ ] Replace `create_board(title) -> BoardSummary` with `save(board: Board) -> Result[None, KanbanError]` (upsert semantics).
- [ ] Replace `update_board(board_id, title) -> Result[BoardSummary, KanbanError]` — remove entirely (absorbed into `save`).
- [ ] Replace `delete_board(board_id) -> Result[None, KanbanError]` with `remove(board_id: str) -> Result[None, KanbanError]`.
- [ ] Rename `get_board(board_id) -> Result[Board, KanbanError]` to `find_by_id(board_id: str) -> Result[Board, KanbanError]`.
- [ ] Keep `find_board_id_by_card` and `find_board_id_by_column` unchanged.

### Phase 4 — Update `KanbanQueryRepositoryPort`

- [ ] Rename `get_board` → `find_by_id`.
- [ ] Rename `list_boards` → `list_all` (optional consistency improvement — decide during implementation).
- [ ] Update `KanbanQueryHandlers` to call `find_by_id` and `list_all`.

### Phase 5 — Refactor `SQLModelKanbanRepository`

- [ ] Implement `save(board: Board)` as a full upsert: insert board row if missing, update if present; same for columns and cards. Absorbs current `create_board`, `update_board`, `save_board` logic.
- [ ] Remove `create_board`, `update_board`, `delete_board` public methods.
- [ ] Rename `get_board` → `find_by_id` (same implementation).
- [ ] Add `remove(board_id)` (same as current `delete_board`).
- [ ] Ensure the class still implements `KanbanRepositoryPort` (run mypy or confirm Protocol structural check).

### Phase 6 — Refactor `InMemoryKanbanRepository`

- [ ] Implement `save(board)` as full upsert: absorbs `create_board`, `update_board`, `save_board`.
- [ ] Remove `create_board`, `update_board`, `delete_board` public methods.
- [ ] Rename `get_board` → `find_by_id`.
- [ ] Add `remove(board_id)`.

### Phase 7 — Refactor `KanbanCommandHandlers`

- [ ] Add `id_gen: IdGenerator` and `clock: Clock` to the `@dataclass` fields.
- [ ] `handle_create_board`: construct `Board(id=self.id_gen.next_id(), title=command.title, created_at=self.clock.now())`, call `self.uow.kanban.save(board)` (no result check — `save` is infallible per ADR-1 in design.md), return `AppOk(AppBoardSummary(id=board.id, title=board.title, created_at=board.created_at))`.
- [ ] `handle_patch_board`: call `find_by_id`, check Err, mutate `board.title`, call `save(board)` (no result check), return `AppOk(AppBoardSummary(...))`.
- [ ] `handle_delete_board`: call `remove(command.board_id)`, check Err, commit, return `AppOk(None)`.
- [ ] `handle_create_column`: replace `str(uuid.uuid4())` with `self.id_gen.next_id()`.
- [ ] `handle_create_card`: replace `str(uuid.uuid4())` with `self.id_gen.next_id()`.
- [ ] Remove direct `import uuid` and `from datetime import datetime, timezone` from handlers (no longer needed).
- [ ] **Do NOT** change `handle_create_board` port return type here — that is owned by change `normalize-command-handler-contracts`.

### Phase 8 — Update DI composition

- [ ] Add `id_gen: IdGenerator` and `clock: Clock` fields to `RuntimeDependencies`.
- [ ] Instantiate `UUIDIdGenerator()` and `SystemClock()` in `compose_runtime_dependencies`.
- [ ] Pass `id_gen` and `clock` through `ConfiguredAppContainer` to `command_handlers_factory`.
- [ ] Update `build_container` in `container.py` to pass `id_gen` and `clock` to `KanbanCommandHandlers`.

### Phase 9 — Add fake adapters and update tests

> **Note**: Updating `handle_create_board` port return type is **not part of this change** — it is owned by change `normalize-command-handler-contracts`. Do not include it here.

- [ ] Create `tests/support/fakes.py` with `FakeIdGenerator` and `FakeClock`.
- [ ] Update `tests/support/kanban_builders.py` (`HandlerHarness`) to wire `FakeIdGenerator` and `FakeClock`.
- [ ] Update `tests/unit/test_kanban_command_handlers.py` to verify created entities have IDs from `FakeIdGenerator`.
- [ ] Update `tests/unit/test_kanban_repository_contract.py` to call `save(board)`, `find_by_id(id)`, `remove(id)`.
- [ ] Update `test_hexagonal_boundaries.py` `test_persistence_adapters_match_repository_port_surface` to reflect new port methods.
- [ ] Run full test suite and fix any remaining failures.
