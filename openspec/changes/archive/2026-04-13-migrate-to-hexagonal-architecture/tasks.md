## 1. Establish Hexagonal Boundaries

- [x] 1.1 Create explicit Kanban layer structure for domain, application, infrastructure, and API adapters.
- [x] 1.2 Move repository protocol and domain rules to core-facing modules with no framework imports.
- [x] 1.3 Add architecture boundary checks (or equivalent tests) to prevent outward dependency violations.

## 2. Introduce Application Use Cases

- [x] 2.1 Define use-case interfaces/handlers for board, column, and card operations.
- [x] 2.2 Implement use-case orchestration using outbound repository ports and domain error/result semantics.
- [x] 2.3 Add unit tests for use cases with fake repository adapters.

## 3. Refactor Inbound HTTP Adapters

- [x] 3.1 Refactor FastAPI route handlers to delegate to application use cases.
- [x] 3.2 Keep request/response schema contracts backward compatible while moving orchestration out of routes.
- [x] 3.3 Keep RFC9457/problem-details mapping in API adapter layer and adapt error translation to use-case outputs.

## 4. Centralize Composition Root Wiring

- [x] 4.1 Move settings-driven backend selection and adapter construction to composition root modules.
- [x] 4.2 Ensure lifespan startup/shutdown manages adapter readiness and close/disposal hooks.
- [x] 4.3 Remove repository-factory and settings coupling from port definition modules.

## 5. Isolate Persistence Adapters

- [x] 5.1 Relocate SQLModel/SQLite/PostgreSQL repository implementations under infrastructure adapter modules.
- [x] 5.2 Keep Alembic and SQLModel metadata wiring functional after module relocation.
- [x] 5.3 Verify SQLite and PostgreSQL adapters both satisfy repository contract tests.

## 6. Preserve Behavior and Complete Migration

- [x] 6.1 Update integration tests and dependency overrides to target new application/composition entry points.
- [x] 6.2 Add temporary compatibility shims where needed, then remove them after parity is validated.
- [x] 6.3 Run full quality checks (unit, integration, e2e, lint/type) and document migration completion criteria.
