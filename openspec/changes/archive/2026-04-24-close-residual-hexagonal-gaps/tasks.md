## 1. Inbound Driver Port Hardening

- [x] 1.1 Define explicit command/query driver-port protocols in `src/application/*` and make concrete handlers implement them.
- [x] 1.2 Refactor `src/api/dependencies.py` and `src/api/kanban_router.py` to depend on driver-port protocols, not concrete handler classes.
- [x] 1.3 Add architecture/unit checks that route dependencies are typed to ports and do not inject repositories directly.

## 2. Transport Schema Ownership

- [x] 2.1 Move wire-facing enum/value types used by Pydantic schemas into `src/api/schemas/*` so schema modules do not import `src.application.contracts`.
- [x] 2.2 Update API mappers to translate between transport schema types and application contract types at the adapter boundary.
- [x] 2.3 Update schema and API tests to preserve existing wire behavior after transport-type decoupling.

## 3. Aggregate Repository Surface Sealing

- [x] 3.1 Remove or internalize public child-entity helper methods from production repository adapters when they are not declared in `KanbanCommandRepository`/`KanbanQueryRepository`.
- [x] 3.2 Refactor `tests/support/kanban_builders.py` and repository-related tests to use aggregate-oriented flows (port operations and/or command handlers).
- [x] 3.3 Narrow container and API dependency exports so inbound adapters receive handlers/ports, not repository access shortcuts.

## 4. Architecture Governance Expansion

- [x] 4.1 Extend `tests/unit/test_hexagonal_boundaries.py` with checks for adapter public-surface parity against repository ports.
- [x] 4.2 Add checks that API schema modules do not import application contract modules directly.
- [x] 4.3 Update architecture documentation to codify the new driver-port, schema-ownership, and adapter-surface rules.

## 5. Iterative Gap Closure (Second Pass)

- [x] 5.1 Move command-handler construction out of `src/api/dependencies.py` into composition-root container factories so API dependencies do not import concrete handler classes.
- [x] 5.2 Refactor `/health` routing to consume dedicated handler/settings dependencies instead of injecting the app container object directly.
- [x] 5.3 Add architecture tests to fail on direct AppContainer injection in routes and concrete handler imports inside API dependency modules.
