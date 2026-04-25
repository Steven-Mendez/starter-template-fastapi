# Tasks: Fix Wire-Format Concerns Leaking into Command and Schema Contracts

**Change ID**: `fix-patch-command-wire-concerns`

---

## Implementation Checklist

### Phase 1 — Fix `CardUpdate.column_id` type

- [ ] In `src/api/schemas/kanban/card_update.py`:
  - Add `from uuid import UUID` import.
  - Change `column_id: str | None = None` → `column_id: UUID | None = None`.
- [ ] In `src/api/mappers/kanban/card.py`, update `to_patch_card_input`:
  - Current: `"column_id": str(updates["column_id"]) if "column_id" in updates else None`
  - After change: this line already correctly calls `str()` on the value — UUID objects will be coerced; confirm no code path receives a non-UUID value.
- [ ] Add a test: `PATCH /api/cards/{valid_id}` with `{"column_id": "not-a-uuid"}` returns 422.

### Phase 2 — Rename `due_at_provided` → `clear_due_at`

- [ ] In `src/application/commands/patch_card.py`:
  - Rename field `due_at_provided: bool = False` → `clear_due_at: bool = False`.
- [ ] In `src/api/mappers/kanban/card.py`, update `PatchCardInput` TypedDict:
  - Rename key `"has_due_at"` → `"clear_due_at"`.
  - Update `to_patch_card_input` return value:
    - Change `"has_due_at": "due_at" in updates`
    - To `"clear_due_at": "due_at" in updates and updates.get("due_at") is None`
    - (True only when `due_at` was explicitly sent as `null`)
- [ ] In `src/api/routers/cards.py`, update `PatchCardCommand(...)` construction:
  - Change `due_at_provided=input_data["has_due_at"]` → `clear_due_at=input_data["clear_due_at"]`.
- [ ] In `src/api/mappers/kanban/card.py`, update `has_patch_card_changes`:
  - Rename `"has_due_at"` key usage → `"clear_due_at"`.

### Phase 3 — Update handler

- [ ] In `src/application/commands/handlers.py`, in `handle_patch_card`:
  - Change `if command.due_at_provided:` → `if command.clear_due_at or command.due_at is not None:`
  - Logic: update `card.due_at` when either a new value is provided OR the caller explicitly wants to clear it.

### Phase 4 — Update tests

- [ ] Search `tests/` for `due_at_provided` — update all occurrences to `clear_due_at`.
- [ ] Search `tests/` for `has_due_at` — update all occurrences.
- [ ] Add test to `tests/unit/test_kanban_schemas.py`:
  - `test_card_update_column_id_must_be_valid_uuid` — assert `ValidationError` when `column_id="not-a-uuid"`.
  - `test_card_update_valid_uuid_column_id` — assert valid UUID string is accepted.
- [ ] Add integration test to `tests/integration/test_kanban_api.py`:
  - `test_patch_card_with_invalid_column_id_returns_422`.

### Phase 5 — Verify semantic correctness

- [ ] Write a test that verifies PATCH with `{}` does NOT change `due_at`.
- [ ] Write a test that verifies PATCH with `{"due_at": null}` DOES clear `due_at`.
- [ ] Write a test that verifies PATCH with `{"due_at": "<iso>"}` DOES set `due_at`.
- [ ] Run `python -m pytest tests/ -x` — all tests pass.
