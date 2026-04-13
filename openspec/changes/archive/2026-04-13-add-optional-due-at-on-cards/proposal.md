## Why

Kanban users often want a planned completion time on a card without changing column workflow. An optional **`due_at`** timestamp lets clients show deadlines, sort or badge in the UI, and integrate with calendars; **list order from the API remains defined only by `position`** (`due_at` does not reorder cards server-side).

## What Changes

- Add an optional `due_at` field on cards (`null` when not set). Values are ISO 8601 datetimes in JSON; the API stores and returns them consistently with the rest of the stack.
- Expose `due_at` on card responses and allow setting or clearing via `POST /api/columns/{column_id}/cards` and `PATCH /api/cards/{id}` (explicit `null` on PATCH clears a previously set due date).
- Extend automated tests following the project testing pyramid (unit store/schemas, integration HTTP, minimal e2e if needed).

## Capabilities

### New Capabilities

- None (behavior extends the existing Kanban domain).

### Modified Capabilities

- `kanban-board`: Card model and HTTP payloads gain optional `due_at`; scenarios for create, read, update (including clear), and nested board detail are updated accordingly.

## Impact

- **Code**: `kanban/schemas.py`, `kanban/store.py`, `kanban/router.py`; unit and integration tests under `tests/`.
- **API**: Request and response JSON for cards include `due_at` (nullable). Existing clients that ignore unknown fields remain compatible; omitted `due_at` on create yields `null`.
