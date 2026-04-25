# Proposal: Fix Wire-Format Concerns Leaking into Command and Schema Contracts

**Change ID**: `fix-patch-command-wire-concerns`
**Priority**: Medium
**Status**: Proposed

---

## Problem Statement

Two distinct wire-format concerns have leaked from the HTTP adapter layer into application and schema contracts.

### Problem A: `PatchCardCommand.due_at_provided: bool` is HTTP patch semantics in a command DTO

```python
@dataclass(frozen=True, slots=True)
class PatchCardCommand:
    card_id: str
    ...
    due_at: datetime | None = None
    due_at_provided: bool = False    # ← HTTP PATCH "field present vs. null" semantics
```

`due_at_provided` exists to distinguish between:
- `PATCH /cards/1 {}` — `due_at` not in payload (do not change due_at)
- `PATCH /cards/1 {"due_at": null}` — `due_at` explicitly nulled out (clear due_at)

This is a **wire format concern** — the distinction between "field absent" and "field explicitly set to null" is an HTTP/JSON property. Application commands should express **business intent**, not encoding details.

The flag is set in the API mapper:
```python
"has_due_at": "due_at" in updates,  # ← model_dump(exclude_unset=True) JSON key check
```

And forwarded to the command:
```python
PatchCardCommand(..., due_at_provided=input_data["has_due_at"])
```

And consumed in the handler:
```python
if command.due_at_provided:
    card.due_at = command.due_at
```

The business intent is: **"set the due date to this value"** (which may be `None`). A cleaner command would use an explicit sentinel or a separate field that names the intent: `clear_due_at: bool = False`. Better still, the command may carry an `Optional[Optional[datetime]]` analog (`due_at: Unset | datetime | None`) to avoid the boolean at all. The simplest clean solution: rename `due_at_provided` → `clear_due_at` and make it explicit business intent:
- `clear_due_at=True, due_at=None` → "I want to remove the due date"
- `clear_due_at=False, due_at=datetime(...)` → "I want to set the due date"
- `clear_due_at=False, due_at=None` → "I am not touching the due date"

Alternatively, use Python 3.13+ `enum.member` or a typed `Update[T]` generic to cleanly express absent vs. null.

### Problem B: `CardUpdate.column_id: str | None` — missing UUID validation

```python
# src/api/schemas/kanban/card_update.py
class CardUpdate(BaseModel):
    ...
    column_id: str | None = None    # ← should be UUID | None
```

All other entity-ID fields in API schemas and path parameters use `UUID`:

| Location | Type |
|---|---|
| `PATCH /cards/{card_id}` path param | `UUID` |
| `GET /boards/{board_id}` path param | `UUID` |
| `POST /boards/{board_id}/columns` path param | `UUID` |
| `CardUpdate.column_id` request body | `str` ← inconsistent |

Pydantic validates path parameters as `UUID` and rejects malformed values. But `column_id` in the request body accepts any string, including non-UUID values. If a caller passes `"not-a-uuid"` as `column_id`, it passes Pydantic validation, reaches the handler, and produces an implicit "column not found" failure at the application layer rather than a proper 422 validation error at the HTTP boundary.

This violates the principle that the HTTP adapter should validate all input before it reaches the application layer.

---

## Rationale

Per `hex-design-guide.md` Section 33:
> "Syntax validation: Is this a UUID? [...] This belongs in Pydantic API schemas."
> "Application validation: Does this user exist? This belongs in use cases."

UUID format validation is syntax validation — it belongs in the Pydantic schema, not in the application layer. Similarly, the `due_at_provided` flag passes HTTP encoding details into the application layer, which should only deal with business intent.

Per Section 8:
> "These models are for HTTP input/output. They are not your domain model."

---

## Scope

**In scope:**
- Rename `PatchCardCommand.due_at_provided` → `clear_due_at` and update all call sites.
- Update the API mapper `to_patch_card_input` to set `clear_due_at=True` when `due_at` is explicitly set to `None` in the payload.
- Update `KanbanCommandHandlers.handle_patch_card` to use `command.clear_due_at`.
- Change `CardUpdate.column_id: str | None` → `UUID | None`.
- Update `to_patch_card_input` mapper to call `str(updates["column_id"])` (converts UUID → str for command).
- Update `src/api/routers/cards.py` if `column_id` is referenced directly.

**Out of scope:**
- Changing `PatchCardCommand` to use a `Update[T]` generic (acceptable future improvement but scope risk).
- Changing other optional fields in `CardUpdate`.

---

## Affected Modules

| File | Change |
|---|---|
| `src/application/commands/patch_card.py` | Modified — rename field, update type |
| `src/api/mappers/kanban/card.py` | Modified — update mapper logic |
| `src/api/routers/cards.py` | Modified — update `PatchCardCommand(...)` construction |
| `src/api/schemas/kanban/card_update.py` | Modified — `column_id: UUID \| None` |
| `src/application/commands/handlers.py` | Modified — use `command.clear_due_at` |
| `tests/unit/test_kanban_command_handlers.py` | Modified — update `PatchCardCommand` with new field name |
| `tests/integration/test_kanban_api.py` | Verified — no direct use of `due_at_provided` |

---

## Proposed Change

`PatchCardCommand`:
```python
@dataclass(frozen=True, slots=True)
class PatchCardCommand:
    card_id: str
    title: str | None = None
    description: str | None = None
    column_id: str | None = None
    position: int | None = None
    priority: AppCardPriority | None = None
    due_at: datetime | None = None
    clear_due_at: bool = False     # ← renamed from due_at_provided; clearer business intent
```

Handler:
```python
if command.clear_due_at or command.due_at is not None:
    card.due_at = command.due_at
```

API mapper:
```python
def to_patch_card_input(body: CardUpdate) -> PatchCardInput:
    updates = body.model_dump(exclude_unset=True)
    ...
    return {
        ...
        "due_at": cast(datetime | None, updates.get("due_at")),
        "clear_due_at": "due_at" in updates and updates["due_at"] is None,
        # ↑ True only when "due_at" was explicitly provided AND is null
    }
```

`CardUpdate` schema:
```python
from uuid import UUID

class CardUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    column_id: UUID | None = None      # ← was str | None
    position: int | None = Field(default=None, ge=0)
    priority: CardPrioritySchema | None = None
    due_at: datetime | None = None
```

Mapper update for `column_id`:
```python
"column_id": str(updates["column_id"]) if "column_id" in updates else None,
# UUID → str conversion happens here, application command stays as str
```

---

## Acceptance Criteria

1. `PatchCardCommand` does not have a field named `due_at_provided`.
2. `PatchCardCommand` has a field `clear_due_at: bool = False`.
3. `CardUpdate.column_id` is typed as `UUID | None`.
4. `PATCH /cards/{id}` with `{"due_at": null}` clears the due date (status 200, `due_at` is null in response).
5. `PATCH /cards/{id}` with `{}` leaves `due_at` unchanged.
6. `PATCH /cards/{id}` with `{"column_id": "not-a-uuid"}` returns 422, not 404 or 409.
7. All existing tests for card patching pass.

---

## Migration Strategy

1. Update `CardUpdate.column_id` to `UUID | None`.
2. Update `to_patch_card_input` mapper — `column_id` conversion now receives a `UUID` object, use `str()`.
3. Rename `due_at_provided` → `clear_due_at` in `PatchCardCommand`. Update `to_patch_card_input` mapper logic.
4. Update `cards.py` router — `due_at_provided=input_data["has_due_at"]` → `clear_due_at=input_data["clear_due_at"]`.
5. Update `handle_patch_card` handler to use `command.clear_due_at`.
6. Update tests — replace `PatchCardCommand(due_at_provided=...)` with `PatchCardCommand(clear_due_at=...)`.
7. Run `python -m pytest tests/ -x`.

---

## Risks and Tradeoffs

| Risk | Mitigation |
|---|---|
| `clear_due_at` semantics differ from `due_at_provided` | `due_at_provided` was True when "due_at" appeared in payload (even if set to a value). `clear_due_at` should be True only when "due_at" is explicitly null. Verify the new mapper condition handles both cases. |
| `column_id` type change breaks existing callers passing strings | Pydantic coerces valid UUID strings to `UUID` objects; callers passing valid UUIDs as strings continue to work. Invalid strings now fail with 422 rather than silently passing. |
