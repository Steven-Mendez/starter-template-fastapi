## 1. Implementation

- [x] 1.1 Add optional `due_at` to Pydantic card schemas (`CardRead`, `CardCreate`, `CardUpdate`) with nullable semantics aligned to PATCH (omit vs explicit null).
- [x] 1.2 Extend in-memory `_Card` and `KanbanStore` (create, read, board detail, update) to persist `due_at`; support clearing `due_at` on update when explicitly set to null.
- [x] 1.3 Wire `kanban/router.py` create/patch handlers; use partial-update semantics for PATCH so omitted `due_at` does not clear an existing value.
- [x] 1.4 Unit tests: schemas validation and store behavior (create default null, set/clear/preserve `due_at`).
- [x] 1.5 Integration tests: HTTP create/patch/get board detail including `due_at` and clear-via-null.
- [x] 1.6 Merge delta `openspec/changes/add-optional-due-at-on-cards/specs/kanban-board/spec.md` into canonical `openspec/specs/kanban-board/spec.md`.
