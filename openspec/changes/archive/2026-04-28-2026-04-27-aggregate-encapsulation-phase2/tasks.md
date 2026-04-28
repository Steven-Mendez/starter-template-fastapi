# Tasks: Aggregate Encapsulation Phase 2

**Change ID**: `2026-04-27-aggregate-encapsulation-phase2`

---

## Implementation Checklist

- [x] Identify remaining direct aggregate-internal mutations in handlers.
- [x] Add domain intent methods for those mutation flows (e.g., targeted card lookup/update helpers, column/card operations).
- [x] Refactor handlers to call new domain intent methods.
- [x] Remove duplicate traversal logic where possible.
- [x] Add unit tests asserting handlers use domain intent methods and preserve current behavior.

## Verification

- [x] `uv run pytest tests/unit/test_kanban_command_handlers.py`
- [x] `uv run pytest tests/unit/domain/`
- [x] `uv run pytest -m "not e2e"`

## Verification Notes

- All listed verification checks pass on current branch state.
