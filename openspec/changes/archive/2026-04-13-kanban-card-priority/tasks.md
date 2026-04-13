## 1. Tests first (TDD, golden pyramid — target mix **5 unit : 3 integration : 2 e2e**)

- [x] 1.1 Unit: `KanbanStore` — default priority, create with priority, `update_card` priority, `get_board` / `get_card` expose priority (`tests/unit/test_kanban_store.py`)
- [x] 1.2 Unit: Pydantic — `CardCreate` / `CardUpdate` validation for `priority` (`tests/unit/test_kanban_schemas.py`)
- [x] 1.3 Integration: HTTP create default and explicit priority, PATCH priority (`tests/integration/test_kanban_api.py`)
- [x] 1.4 E2E: live server create and PATCH card priority (`tests/e2e/test_running_server_contracts.py` or new focused module)

## 2. Implementation

- [x] 2.1 Add `CardPriority` and extend `CardRead` / `CardCreate` / `CardUpdate` in `kanban/schemas.py`
- [x] 2.2 Extend `_Card`, `create_card`, `update_card`, and all `CardRead` constructions in `kanban/store.py`
- [x] 2.3 Wire `priority` in `kanban/router.py` (`create_card`, `patch_card` empty-field guard)

## 3. Canonical spec

- [x] 3.1 Merge delta into `openspec/specs/kanban-board/spec.md` (align requirements with implemented behavior)
