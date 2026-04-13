## 1. Domain types

- [x] 1.1 Add `kanban/result.py` with `Ok`, `Err`, and `Result` type alias plus combinators (`unwrap`, `expect`, etc.)
- [x] 1.2 Add `kanban/errors.py` with `KanbanError` `StrEnum` and stable HTTP `detail` strings

## 2. Store and HTTP

- [x] 2.1 Implement `InMemoryKanbanRepository` in `kanban/repository.py` returning `Result` for fallible methods; `kanban/store.py` re-exports compatibility names
- [x] 2.2 Update `kanban/router.py` to match on `Result` and map `KanbanError.detail` to HTTP 404 responses
- [x] 2.3 Update `tests/unit/test_kanban_store.py`; all tests green

## 3. Specs

- [x] 3.1 On archive: merge delta `openspec/changes/kanban-result-pattern/specs/result-pattern/spec.md` into `openspec/specs/result-pattern/spec.md` (create capability folder if missing)
