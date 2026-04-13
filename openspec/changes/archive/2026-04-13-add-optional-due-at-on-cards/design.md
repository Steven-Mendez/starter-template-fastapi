## Context

The Kanban stack is in-memory FastAPI + Pydantic v2. Cards already have `position` for ordering within a column and `priority` as metadata. **`due_at` is orthogonal metadata**: it does not change `position` sorting in board detail.

## Goals / Non-Goals

**Goals:**

- Represent `due_at` as an optional timezone-aware datetime in Python, serialized as ISO 8601 in JSON (Pydantic `datetime`).
- Default new cards to `due_at: null` when the field is omitted on create.
- Allow PATCH to set a datetime or clear with explicit `null`; omitted `due_at` on PATCH leaves the stored value unchanged (use `model_dump(exclude_unset=True)` / fields-set semantics).
- Keep store and schema changes minimal and testable with TDD.

**Non-Goals:**

- Sorting or filtering boards by due date (query params, indexes).
- Reminders, notifications, or background jobs.
- Database persistence or migrations.

## Decisions

1. **Type**: `datetime | None` on card models; JSON uses standard datetime strings. Prefer normalizing to UTC in the store for naive inputs if needed for consistency (minimal: accept Pydantic-parsed datetimes as returned).
2. **Default**: `null` when omitted on create.
3. **PATCH clear**: Client sends `"due_at": null` to clear; omission means no change to `due_at`.
4. **Ordering**: Column card lists in `GET /api/boards/{id}` remain sorted by `position` only.

## Risks / Trade-offs

- [Clients assume due date affects order] → Spec states order is still by `position` only.
- [Timezone confusion] → Document ISO 8601; template uses Pydantic/FastAPI defaults for serialization.

## Migration Plan

- Not applicable (in-memory). Deploy is replace-and-run.

## Open Questions

- None for this scope.
