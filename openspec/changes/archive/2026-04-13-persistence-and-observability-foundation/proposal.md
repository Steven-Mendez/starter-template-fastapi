## Why

The current in-memory repository is useful for demos but limits durability, scale, and realistic production behavior. We also need a minimum observability baseline so operators can diagnose failures without attaching a debugger.

## What Changes

- Introduce a persistent SQLite-backed implementation behind the existing `KanbanRepository` protocol.
- Add repository selection through configuration, keeping in-memory mode available for fast local runs/tests.
- Establish structured application logging with request correlation fields.
- Expand health reporting to include persistence readiness signals.

## Capabilities

### New Capabilities
- `kanban-sqlite-storage`: Persist board/column/card state in SQLite while preserving repository contract behavior.
- `api-observability-baseline`: Emit structured logs and expose richer operational health signals.

### Modified Capabilities
- `kanban-repository`: Extend repository abstraction to support configured backend selection and parity tests across implementations.

## Impact

- Affected files: `kanban/repository.py`, new persistence modules, settings/config, `main.py`, and health-related endpoints/tests.
- Adds runtime dependency for SQL persistence stack and potential migrations/bootstrap code.
- Increases implementation scope and requires repository contract tests to avoid behavioral drift.
