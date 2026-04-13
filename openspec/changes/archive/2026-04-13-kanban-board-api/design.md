## Context

The project is a FastAPI service (`main.py`) with OpenAPI docs. There is no persistence layer yet; data must live in process memory and reset on restart.

## Goals / Non-Goals

**Goals:**

- Expose a clear REST surface for boards → columns → cards.
- Validate inputs and serialize responses with Pydantic v2 (`BaseModel`, `Field`, `ConfigDict` where useful).
- Keep a small in-memory store behind a narrow Python API so routes stay thin and tests can target HTTP behavior.
- Practice TDD: tests specify observable API behavior (status codes, JSON shape, error cases).

**Non-Goals:**

- Authentication, multi-tenant isolation, or durable storage.
- WebSockets, real-time collaboration, or optimistic concurrency tokens.
- Pagination for list endpoints (small in-memory lists only).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| IDs | UUID strings (RFC 4122) as `str` in JSON | URL-safe, opaque, easy with Pydantic and OpenAPI. |
| Route layout | `/api/boards`, nested `/api/boards/{board_id}/columns`, `/api/columns/{column_id}/cards`, plus `/api/cards/{id}` for patch/delete/move | RESTful grouping; card move uses `PATCH` on the card with optional `column_id` and `position`. |
| Ordering | Integer `position` per column for cards and per board for columns | Simple reordering without a separate ordering service. |
| Store | Module-level dicts + helper class in `kanban/store.py` | Minimal; swap for DB later without changing Pydantic models. |
| Errors | `404` for missing resources; `422` for validation (FastAPI default) | Standard HTTP semantics. |

**Alternatives considered:** SQLModel/SQLite (rejected: user asked for in-memory only). Single flat `/items` API (rejected: poor fit for Kanban).

## Risks / Trade-offs

- **Process memory** — All data is lost on restart → Acceptable for the stated scope; document in README if needed later.
- **No locking** — Concurrent requests could race on position updates → Acceptable for a dev template; production would use transactions.

## Migration Plan

Not applicable (new endpoints only).

## Open Questions

- None.
