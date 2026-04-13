## Context

The service uses FastAPI and an in-memory `KanbanStore`. Routes currently branch on `if not x` / `is None` after store calls and raise `HTTPException` with fixed strings. The OpenSpec change `kanban-result-pattern` adds specification-driven design and test-driven implementation of a Result-style API without altering the external Kanban HTTP contract.

## Goals / Non-Goals

**Goals:**

- Provide `Ok[T]` / `Err[E]` and a `Result[T, E]` alias with a minimal, predictable API (constructors, predicates, `map`, `map_err`, `and_then`, `unwrap` / `expect`).
- Use `KanbanError` as a small, immutable carrier for HTTP-facing `detail` text (and 404 as the default status for “missing or invalid target” cases, matching current behavior).
- Refactor fallible store methods to return `Result` so the router centralizes error mapping.

**Non-Goals:**

- General-purpose async Result, I/O, or third-party `returns`-style dependency.
- Changing OpenAPI models, routes, or status codes for existing Kanban scenarios.
- Using exceptions for non-exceptional domain failures inside the store (errors are values).

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Result shape | Frozen dataclasses `Ok`/`Err` and `type Result[T,E] = Ok[T] \| Err[E]` | Clear tags, pattern-matching friendly, zero magic. |
| Combinators | Module-level functions (`result_map`, `result_and_then`, …) | Avoid duplicating methods on both variants; keeps variants as dumb data. |
| Kanban errors | `@dataclass(frozen=True) KanbanError` with `detail: str` | Router maps to `HTTPException`; same strings as today for integration parity. |
| Void success | `Ok(None)` for delete-style operations | Aligns with Python `None` as “success with no payload”. |

**Alternatives considered:** `typing.Never` / exceptions for control flow (rejected: user asked for result pattern). Single-class `Result` with optional fields (rejected: weaker typing and easier misuse).

## Risks / Trade-offs

- **Boilerplate** — More typing at call sites than raw `Optional`. **Mitigation:** `match` / small router helper keeps routes readable.
- **Learning curve** — New contributors must learn `Result`. **Mitigation:** Short spec, focused tests, and consistent router mapping.

## Migration Plan

Not applicable: in-memory template; deploy is replace code and run tests.

## Open Questions

- None for this scope.
