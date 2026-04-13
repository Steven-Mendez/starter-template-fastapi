## Context

The project uses a repository protocol with an in-memory default instance, which is simple but non-durable. Operational feedback is also minimal; troubleshooting currently depends on ad hoc local inspection rather than structured logs and explicit readiness checks.

## Goals / Non-Goals

**Goals:**
- Add a persistent repository backend while preserving existing route contracts.
- Keep in-memory repository support for low-friction local workflows.
- Introduce practical observability primitives (structured logs + readiness health data).

**Non-Goals:**
- Build full multi-tenant or high-throughput database scaling strategies.
- Introduce full telemetry stack (metrics backends, tracing exporters) in this iteration.
- Redesign kanban domain entities.

## Decisions

- Implement SQLite repository behind the existing `KanbanRepository` protocol to minimize API-layer changes.
- Use repository contract tests to enforce behavior parity between in-memory and SQLite implementations.
- Select repository backend via settings (`inmemory` vs `sqlite`) to allow gradual rollout.
- Add structured logging fields (request ID, path, method, status, latency) for every request.
- Extend `/health` to expose persistence readiness state without leaking sensitive internals.

## Risks / Trade-offs

- [Database layer increases code complexity] -> Keep persistence bounded to repository module and verify with contract tests.
- [SQLite locking/concurrency limits] -> Document starter-template limitations and keep backend swappable for future PostgreSQL upgrade.
- [More operational output can be noisy] -> Use configurable log levels and stable field names.
