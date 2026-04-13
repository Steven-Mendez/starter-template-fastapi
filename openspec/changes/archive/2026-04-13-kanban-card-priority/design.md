## Context

The Kanban stack is in-memory FastAPI + Pydantic v2. Cards already have `position` for ordering within a column. Priority is orthogonal metadata: it does not change `position` sorting in board detail (cards stay ordered by ascending `position` as today).

## Goals / Non-Goals

**Goals:**

- Represent priority as a small closed set of string values in JSON for clarity and stable API contracts.
- Default new cards to `medium` when `priority` is omitted on create.
- Keep store and schema changes minimal and testable with TDD.

**Non-Goals:**

- Sorting or filtering boards by priority (query params, indexes).
- Priority-based reordering rules competing with `position`.
- Database persistence or migrations.

## Decisions

1. **Values**: Use `low`, `medium`, `high` (lowercase strings). Maps cleanly to UI labels and avoids integer magic numbers.
2. **Default**: `medium` for create when the field is absent; PATCH may set any allowed value explicitly.
3. **Ordering**: Column card lists in `GET /api/boards/{id}` remain sorted by `position` only; priority is returned on each card for clients to use.
4. **Implementation**: Python `StrEnum` (or equivalent) shared by Pydantic models and store for a single source of truth.

## Risks / Trade-offs

- [Clients assume priority affects order] → Document in spec that order is still by `position`; clients may sort by priority if needed.
- [Extra field on every card payload] → Small JSON cost; acceptable for this template.

## Migration Plan

- Not applicable (in-memory). Deploy is replace-and-run.

## Open Questions

- None for this scope.
