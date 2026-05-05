# Feature template

This directory is the **canonical scaffold** to copy when adding a new feature.
Search for `TODO(template):` after copying — every placeholder is marked.

> The reference implementation lives in [`src/features/kanban/`](../kanban/).
> Read it side-by-side while following this guide.

## 11-step recipe

### 1. Copy and rename

```bash
cp -r src/features/_template src/features/<your_feature>
rg -l 'features\._template\|template_' src/features/<your_feature> \
  | xargs sed -i '' \
    -e 's|features\._template|features.<your_feature>|g' \
    -e 's|TemplateContainer|<YourFeature>Container|g' \
    -e 's|register_template|register_<your_feature>|g'
```

### 2. Define the domain aggregate

Edit `domain/models/<aggregate>.py`. Keep it pure: no FastAPI / SQLModel / Pydantic
imports. Use `Result[T, E]` from `src.platform.shared.result` for failure paths.

> Reference: [`src/features/kanban/domain/models/board.py`](../kanban/domain/models/board.py)

### 3. Declare outbound ports

In `application/ports/outbound/`, define one `Protocol` per side effect:
repositories, gateways, message buses, etc. Adapter implementations live under
`adapters/outbound/`.

> Reference: [`src/features/kanban/application/ports/outbound/`](../kanban/application/ports/outbound/)

### 4. Declare inbound port Protocols

In `application/ports/inbound/`, declare one `Protocol` per use case (named
`<UseCase>UseCasePort`). The HTTP adapter depends on the Protocol, never on the
concrete class.

> Reference: [`src/features/kanban/application/ports/inbound/`](../kanban/application/ports/inbound/)

### 5. Define commands, queries, contracts and errors

- `commands/` — input DTOs for state-changing use cases.
- `queries/` — input DTOs for read use cases.
- `contracts/` — output DTOs (`AppFoo`, `AppBar`) returned by use cases.
- `errors.py` — `ApplicationError` enum + `from_domain_error()`.

> Reference: [`src/features/kanban/application/`](../kanban/application/)

### 6. Implement use cases

Use cases are `@dataclass(slots=True)` classes with port fields and an
`execute(...) -> Result[T, ApplicationError]` method. They orchestrate domain
behavior; no framework imports allowed.

> Reference: [`src/features/kanban/application/use_cases/`](../kanban/application/use_cases/)

### 7. Implement outbound adapters

Concrete implementations of outbound ports live in `adapters/outbound/`:
- `persistence/sqlmodel/` for SQL persistence,
- `query/` for read-side projections,
- gateways for external APIs, etc.

> Reference: [`src/features/kanban/adapters/outbound/`](../kanban/adapters/outbound/)

### 8. Implement the inbound HTTP adapter

Under `adapters/inbound/http/`:
- `schemas/` — Pydantic IO models,
- `mappers/` — schema ↔ command/query/contract conversions,
- `errors.py` — RFC 9457 ApplicationError → HTTP mapping,
- one router file per resource, **split into `*_read_router` and `*_write_router`**
  (the latter has `dependencies=[RequireWriteApiKey]`),
- `router.py` — composes the feature's API surface under `/api`.

> Reference: [`src/features/kanban/adapters/inbound/http/`](../kanban/adapters/inbound/http/)

Always:
- declare return types on path operations (no redundant `response_model=`),
- use `Annotated[..., Depends(...)]` and `TypeAlias` for DI,
- never import another feature.

### 9. Wire the composition root

Build a `<Feature>Container` in `composition/container.py` whose factory methods
return inbound `Port` types (so consumers see only the abstraction). Implement
`register_<feature>(app, platform)` in `composition/wiring.py`.

> Reference: [`src/features/kanban/composition/`](../kanban/composition/)

### 10. Register the feature in `src/main.py`

Add the import and a call in the lifespan:

```python
from src.features.<your_feature>.composition import (
    build_<your_feature>_container,
    register_<your_feature>,
)

# inside create_app() / lifespan
container = build_<your_feature>_container(...)
register_<your_feature>(app, container)
```

### 11. Write tests

Tests live under `src/features/<your_feature>/tests/` (co-located with the feature).
Order matters:

1. `tests/fakes/` — implement in-memory adapters for every outbound port.
2. `tests/unit/domain/` — pure tests for aggregates, value objects and specs.
3. `tests/unit/application/` — use case tests with fakes + a `RecordingUoW` to
   assert commit/rollback semantics.
4. `tests/contracts/` — port contract suites that run against both fakes and
   real adapters.
5. `tests/integration/` — adapters against testcontainers / real infrastructure
   (mark `@pytest.mark.integration`).
6. `tests/e2e/` — `TestClient` flows with `app.dependency_overrides`
   (mark `@pytest.mark.e2e`).

Run them:

```bash
make test                          # unit + e2e (fast, no docker)
make test-integration              # docker-backed
make test-feature FEATURE=<your_feature>
```

> Reference: [`src/features/kanban/tests/`](../kanban/tests/)

## Conformance

Every feature is enforced by import-linter contracts in `pyproject.toml`:
- domain has no framework or outward imports,
- application has no adapter or framework imports,
- inbound and outbound adapters do not couple to each other,
- features cannot import each other,
- platform never imports features.

Run `make lint-arch` after each step.

## Gotchas

- Do not reach across features. If two features share a concept, lift it into
  `src/platform/shared/` (truly cross-cutting) or expose it through ports.
- Do not register `_template/` itself in `src/main.py`. Copy it first.
- Keep `TODO(template):` markers in placeholder files until you replace them.
