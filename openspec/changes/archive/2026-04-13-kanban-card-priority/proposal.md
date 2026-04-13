## Why

Kanban users need to signal urgency or importance on cards without changing column workflow. Adding an explicit priority lets clients filter, badge, or group work; **list order from the API remains defined only by `position`** (priority does not reorder cards server-side).

## What Changes

- Add a `priority` field on cards with allowed values `low`, `medium`, and `high`, defaulting to `medium` when omitted on create.
- Expose `priority` on card responses and allow updates via `PATCH /api/cards/{id}`.
- Extend automated tests following the project testing pyramid (heavy unit coverage, fewer integration checks, minimal e2e smoke).

## Capabilities

### New Capabilities

- None (behavior extends the existing Kanban domain).

### Modified Capabilities

- `kanban-board`: Card model and HTTP payloads gain priority; scenarios for create, read, and update are updated accordingly.

## Impact

- **Code**: `kanban/schemas.py`, `kanban/store.py`, `kanban/router.py`; unit, integration, and e2e tests under `tests/`.
- **API**: Request and response JSON for cards include `priority`; existing clients that ignore unknown fields remain compatible; clients sending only legacy fields get default priority on create.
