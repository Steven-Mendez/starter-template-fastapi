# Feature Template Guide

This guide explains how to use `src/features/_template` to add a feature that
matches the current architecture.

The template package is intentionally inert. It is not imported or registered by
`src/main.py`.

## When To Use The Template

Use the template when adding a new bounded feature under `src/features/`.

Do not modify `_template` directly for product behavior. Copy it first.

## Copy The Template

```bash
cp -R src/features/_template src/features/<feature_name>
```

After copying, replace package names and template type names inside the copied
feature. Search for placeholders:

```bash
grep -R -E 'src\.features\._template|TemplateContainer|register_template|ExampleAggregate|ExampleRepositoryPort|GetExampleUseCase' src/features/<feature_name>
```

Replace any matches for:

- `src.features._template`
- `TemplateContainer`
- `register_template`
- `ExampleAggregate`
- `ExampleRepositoryPort`
- `GetExampleUseCase`

Then run Ruff against the copied feature:

```bash
uv run ruff check src/features/<feature_name>
```

## Build The Domain Layer

Put pure business types under:

```text
src/features/<feature_name>/domain/
```

Rules:

- Do not import FastAPI, Pydantic, SQLModel, SQLAlchemy, Alembic, or platform API
  modules.
- Put business invariants on aggregates and entities.
- Return `Result[T, E]` for expected domain failures when the existing code style
  calls for explicit failure handling.

Use `src/features/kanban/domain/` as the reference implementation.

## Build The Application Layer

Put orchestration code under:

```text
src/features/<feature_name>/application/
```

Use this structure:

| Directory | Purpose |
| --- | --- |
| `commands/` | Input DTOs for state-changing use cases. |
| `queries/` | Input DTOs for read use cases. |
| `contracts/` | Output DTOs returned by use cases. |
| `ports/inbound/` | Protocols used by inbound adapters. |
| `ports/outbound/` | Protocols implemented by outbound adapters. |
| `use_cases/` | Application services that coordinate domain and ports. |
| `errors.py` | Application error enum and domain error mapping. |

Use cases should depend on ports through constructor injection and return
`Result[T, ApplicationError]` for expected failures.

## Build Inbound HTTP Adapters

Put FastAPI-facing code under:

```text
src/features/<feature_name>/adapters/inbound/http/
```

Use this structure:

| File or directory | Purpose |
| --- | --- |
| `schemas/` | Pydantic request and response models. |
| `mappers/` | Conversion between transport schemas and application DTOs. |
| `dependencies.py` | FastAPI dependency aliases resolving use case ports from the feature container. |
| `errors.py` | Application error to HTTP Problem Details mapping. |
| resource router files | One or more `APIRouter` instances grouped by resource. |
| `router.py` | Feature router composition. |

For write endpoints that need the shared API key behavior, put routes on a router
with:

```python
APIRouter(dependencies=[RequireWriteApiKey])
```

Read routes should stay on routers without that dependency unless the feature
requires different behavior.

## Build Outbound Adapters

Put infrastructure adapters under:

```text
src/features/<feature_name>/adapters/outbound/
```

For SQLModel persistence, follow the Kanban pattern:

- SQLModel table classes under `persistence/sqlmodel/models/`.
- Domain/table mappers in `persistence/sqlmodel/mappers.py`.
- Repository implementations in `persistence/sqlmodel/repository.py`.
- Unit of work implementation in `persistence/sqlmodel/unit_of_work.py`.

If the feature needs database schema, add Alembic migrations under
`alembic/versions/`.

## Build The Composition Root

Put feature wiring under:

```text
src/features/<feature_name>/composition/
```

The current Kanban feature uses this pattern:

- A feature container class exposes factory methods returning inbound port
  protocols.
- `mount_<feature>_routes(app)` mounts routes when the app is built.
- `attach_<feature>_container(app, container)` stores the container during
  lifespan startup.
- `register_<feature>(app, container)` can exist as a convenience helper, but
  `src/main.py` currently mounts routes before lifespan and attaches containers
  during lifespan.

## Register The Feature

Update `src/main.py` after the new feature has real routes and a real container.

Follow the current separation:

1. Mount routes immediately after building the FastAPI app.
2. Build and attach containers inside the lifespan context.
3. Shut down feature resources in the lifespan `finally` block.

## Add Tests

Place tests under:

```text
src/features/<feature_name>/tests/
```

Recommended structure:

| Directory | Purpose |
| --- | --- |
| `fakes/` | In-memory adapters, fake containers, clocks, ID generators, and UoW fakes. |
| `unit/domain/` | Pure domain tests. |
| `unit/application/` | Use case tests with fakes. |
| `contracts/` | Reusable adapter contract suites. |
| `integration/` | Tests against real infrastructure through testcontainers. |
| `e2e/` | FastAPI `TestClient` flows. |

Run feature tests:

```bash
make test-feature FEATURE=<feature_name>
```

Run architecture contracts:

```bash
make lint-arch
```

## Before Registering A New Feature

- All template placeholders in the copied feature have been replaced.
- The copied feature imports its own package, not `src.features._template`.
- The feature does not import another feature.
- Domain and application layers pass import-linter contracts.
- Unit and e2e tests pass.
- Integration tests pass if persistence was added.
