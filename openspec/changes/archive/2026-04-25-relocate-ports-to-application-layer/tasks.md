# Tasks: Relocate Repository Ports to the Application Layer

**Change ID**: `relocate-ports-to-application-layer`

---

## Implementation Checklist

### Phase 1 — Create new port files

- [ ] Create `src/application/ports/__init__.py` with re-exports for all three port protocols.
- [ ] Create `src/application/ports/kanban_command_repository.py`:
  - Copy `KanbanCommandRepositoryPort` Protocol from `src/domain/kanban/repository/command.py`.
  - Update internal imports to use `src.domain.kanban.models` and `src.domain.shared`.
- [ ] Create `src/application/ports/kanban_query_repository.py`:
  - Copy `KanbanQueryRepositoryPort` Protocol from `src/domain/kanban/repository/query.py`.
  - Update internal imports.
- [ ] Create `src/application/ports/kanban_repository.py`:
  - Copy `KanbanRepositoryPort` composite Protocol.
  - Import from the two new port files (not from domain).

### Phase 2 — Update all import sites

- [ ] `src/application/shared/unit_of_work.py`: update import of `KanbanCommandRepositoryPort`.
- [ ] `src/application/commands/handlers.py`: confirm no direct repository port import (already imports through UoW protocol); if any port import exists, update it.
- [ ] `src/application/queries/handlers.py`: update import of `KanbanQueryRepositoryPort`.
- [ ] `src/infrastructure/persistence/in_memory_repository.py`: update import of `KanbanRepositoryPort`.
- [ ] `src/infrastructure/persistence/sqlmodel_repository.py`: update import of `KanbanRepositoryPort`.
- [ ] `src/infrastructure/config/di/composition.py`: update import of `KanbanRepositoryPort`.
- [ ] `tests/unit/test_hexagonal_boundaries.py`: update import of `KanbanCommandRepositoryPort`, `KanbanQueryRepositoryPort`, `KanbanRepositoryPort`.
- [ ] `tests/unit/test_kanban_repository_contract.py`: no direct port import expected; verify and update if present.
- [ ] `tests/unit/test_kanban_store.py`: update import of `KanbanRepositoryPort as KanbanStore` (line 10).
- [ ] `tests/unit/conftest.py`: update import of `KanbanRepositoryPort` (line 11) and the `store_builder` fixture type cast.
- [ ] `tests/conftest.py`: update import of `KanbanRepositoryPort` (line 9) used to annotate the `kanban_store` fixture return type.
- [ ] `tests/unit/test_hexagonal_boundaries.py`: update imports of `KanbanRepositoryPort`, `KanbanCommandRepositoryPort`, `KanbanQueryRepositoryPort`.
- [ ] Search project-wide for `src.domain.kanban.repository` to catch any remaining import sites.

### Phase 3 — Remove old port files

- [ ] Delete `src/domain/kanban/repository/command.py`.
- [ ] Delete `src/domain/kanban/repository/query.py`.
- [ ] Delete `src/domain/kanban/repository/base.py`.
- [ ] Delete `src/domain/kanban/repository/__init__.py`.
- [ ] Delete `src/domain/kanban/repository/` directory.

### Phase 4 — Update tests and documentation

- [ ] Add `test_domain_does_not_contain_port_modules` to `tests/unit/test_hexagonal_boundaries.py` that asserts `src/domain/kanban/repository/` does not exist.
- [ ] Update `DENY_MATRIX` in `test_hexagonal_boundaries.py` if any exemption for domain repository paths existed.
- [ ] Update `docs/architecture.md` — change "Current Package Map" to reflect `src/application/ports/` instead of `src/domain/kanban/repository/`.
- [ ] Run `python -m pytest tests/ -x` and confirm all tests pass.

### Phase 5 — Verify

- [ ] Run `python -m pytest tests/unit/test_hexagonal_boundaries.py -v` — all architecture tests pass.
- [ ] Run `python -c "from src.application.ports import KanbanCommandRepositoryPort, KanbanQueryRepositoryPort, KanbanRepositoryPort"` — imports succeed.
- [ ] Confirm `python -c "import src.domain.kanban.repository"` raises `ModuleNotFoundError`.
