## Why

The current Kanban implementation mixes domain logic, framework concerns, and repository wiring in the same modules, which makes architectural boundaries hard to enforce as the codebase grows. We need to migrate now to a hexagonal architecture so business rules remain framework-agnostic, easier to test, and safer to evolve.

## What Changes

- Introduce explicit hexagonal layers for `domain`, `application`, and `infrastructure` with inward dependency direction.
- Add application use cases as primary ports between API adapters and domain/repository ports.
- Move repository construction and backend selection from feature modules into a dedicated composition root.
- Refactor FastAPI routes into thin primary adapters that call use cases instead of repositories directly.
- Separate outbound repository ports from concrete SQLModel/SQLite/PostgreSQL adapters.
- Preserve current API behavior and contract tests during migration through compatibility shims where needed.

## Capabilities

### New Capabilities
- `hexagonal-layer-boundaries`: Defines enforceable dependency boundaries between domain, application, and infrastructure layers.
- `kanban-application-use-cases`: Defines use-case interfaces and handlers for Kanban operations consumed by API adapters.
- `composition-root-wiring`: Defines centralized runtime wiring for selecting and instantiating adapters from settings.

### Modified Capabilities
- `api-core`: Route handlers delegate to application use cases and keep transport concerns only.
- `kanban-repository`: Repository contracts are positioned as outbound ports and decoupled from framework/config wiring.
- `kanban-board`: Board workflows continue to behave the same while being orchestrated through use cases.
- `kanban-sqlite-storage`: SQLite persistence remains compliant while moved behind infrastructure adapters.
- `sqlmodel-postgresql-persistence`: PostgreSQL SQLModel adapter remains compliant under the new port/adapter boundaries.

## Impact

- Affected code: `kanban/`, `dependencies.py`, `main.py`, persistence modules, and related tests.
- Affected tests: unit contract tests, repository selection tests, integration tests using dependency overrides.
- Runtime impact: no intended API contract changes; internal wiring and module ownership will change significantly.
- Engineering impact: enables parallel feature work with lower coupling and clearer ownership boundaries.
