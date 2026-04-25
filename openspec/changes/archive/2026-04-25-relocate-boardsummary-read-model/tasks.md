# Tasks: Relocate `BoardSummary` Read Model from Domain to Application Layer

**Change ID**: `relocate-boardsummary-read-model`
**Must be applied after**: `relocate-ports-to-application-layer`, `aggregate-repository-and-infrastructure-ports`

---

## Implementation Checklist

### Phase 1 — Update repository port return type

- [ ] In `src/application/ports/kanban_query_repository.py`:
  - Add `from src.application.contracts import AppBoardSummary`.
  - Change `list_all()` return type from `list[BoardSummary]` to `list[AppBoardSummary]`.
  - Remove `from src.domain.kanban.models import BoardSummary` import (if present).

### Phase 2 — Update `SQLModelKanbanRepository`

- [ ] In `src/infrastructure/persistence/sqlmodel_repository.py`:
  - Add `from src.application.contracts import AppBoardSummary`.
  - Update `list_all()` (formerly `list_boards()`) to construct and return `AppBoardSummary` instead of `BoardSummary`.
  - Remove `from src.domain.kanban.models import BoardSummary` import line (the domain `BoardSummary` is no longer needed here).

### Phase 3 — Update `InMemoryKanbanRepository`

- [ ] In `src/infrastructure/persistence/in_memory_repository.py`:
  - Add `from src.application.contracts import AppBoardSummary`.
  - Update `list_all()` to construct and return `AppBoardSummary`.
  - Remove `from src.domain.kanban.models import BoardSummary` import.

### Phase 4 — Update `KanbanQueryHandlers`

- [ ] In `src/application/queries/handlers.py`:
  - Update `handle_list_boards()` — remove `to_app_board_summary` mapper call. Return `self.repository.list_all()` directly (already `list[AppBoardSummary]`).
  - Remove `to_app_board_summary` import from `src.application.contracts.mappers`.

### Phase 5 — Remove `to_app_board_summary` mapper

- [ ] In `src/application/contracts/mappers.py`:
  - Remove the `to_app_board_summary` function.
  - Remove `BoardSummary` import from `src.domain.kanban.models`.
  - Update `__init__.py` exports of `mappers` if `to_app_board_summary` is re-exported.

### Phase 6 — Remove `BoardSummary` from domain

- [ ] In `src/domain/kanban/models/__init__.py`:
  - Remove `from src.domain.kanban.models.board_summary import BoardSummary`.
  - Remove `"BoardSummary"` from `__all__`.
- [ ] Delete `src/domain/kanban/models/board_summary.py`.

### Phase 7 — Update all call sites

- [ ] Search for `BoardSummary` across the entire project: `rg "BoardSummary" src/ tests/`.
- [ ] Update each remaining reference:
  - `tests/support/kanban_builders.py`: `StoreBuilder.board()` returns a constructed `AppBoardSummary` (not `BoardSummary`).
  - `tests/unit/test_kanban_store.py`: update imports and any direct `BoardSummary` references.
  - `tests/unit/test_kanban_repository_contract.py`: update repository contract protocol to use `AppBoardSummary`.

### Phase 8 — Verify

- [ ] Run `rg "BoardSummary" src/` — expect zero results (from domain location).
- [ ] Run `rg "from src\.domain\.kanban\.models import.*BoardSummary" .` — expect zero results.
- [ ] Run `python -m pytest tests/ -x` — all tests pass.
- [ ] Run `python -m pytest tests/unit/test_hexagonal_boundaries.py -v` — boundary tests pass.
