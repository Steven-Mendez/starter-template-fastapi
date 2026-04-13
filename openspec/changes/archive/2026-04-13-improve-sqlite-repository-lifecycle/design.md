## Context

`SQLiteKanbanRepository` opens a persistent sqlite connection per instance. Multiple tests instantiate repositories and app containers, but connection disposal is not consistently guaranteed.

## Goals / Non-Goals

**Goals:**
- Provide explicit, idempotent close behavior for SQLite repository.
- Ensure lifecycle-managed app shutdown closes repository resources.
- Ensure tests cleanly close repositories they instantiate.

**Non-Goals:**
- Introduce connection pooling.
- Replace sqlite driver.
- Change endpoint behavior or persistence schema.

## Decisions

- Add `close()` to `SQLiteKanbanRepository`, plus context manager (`__enter__`, `__exit__`) support.
- Keep close idempotent so repeated cleanup calls are safe.
- Use FastAPI lifespan to close repository on app shutdown when the repository exposes `close`.
- Update test fixtures/factories to register and close sqlite repositories after use.

## Risks / Trade-offs

- [Additional lifecycle code path] -> Keep close semantics minimal and heavily tested.
- [Potential close-after-use bugs] -> Use idempotent close and ensure cleanup happens in fixture teardown.
