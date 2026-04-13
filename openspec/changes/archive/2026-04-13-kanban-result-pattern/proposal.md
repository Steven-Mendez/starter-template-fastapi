## Why

Domain operations in `KanbanStore` signal failure with `None` or booleans, which forces callers to remember what each sentinel means and scatters ad hoc checks. A typed **Result** sum type makes success and failure explicit, improves composability (`map`, `and_then`), and lets the HTTP layer map structured errors to status codes and messages in one place without changing the public REST contract.

## What Changes

- Add a small reusable `Result[T, E]` type with `Ok` / `Err` variants and common combinators (`map`, `map_err`, `and_then`, `unwrap`, etc.).
- Introduce `KanbanError` (or equivalent) as the error type for fallible store operations.
- Refactor `KanbanStore` methods that currently return `Optional` or `bool` for failure to return `Result` instead.
- Update the Kanban router to translate `Err` values to `HTTPException` while preserving existing status codes and response bodies for clients.

## Capabilities

### New Capabilities

- `result-pattern`: Typed `Result`/`Ok`/`Err` for explicit success or failure, with combinators suitable for domain and HTTP mapping.

### Modified Capabilities

- None (HTTP behavior and JSON shapes for the Kanban API remain unchanged; this is an internal implementation pattern).

## Impact

- **New modules**: `kanban/result.py`, `kanban/errors.py` (or equivalent placement).
- **Modified**: `kanban/store.py`, `kanban/router.py`.
- **Tests**: New unit tests for `Result`; existing Kanban unit and integration tests updated or unchanged behavior-wise.
