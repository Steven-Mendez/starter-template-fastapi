# Architecture

This document explains how the service is structured and how requests move
through the system.

## Overview

The repository uses a feature-first hexagonal architecture.

The `platform` package owns cross-cutting application concerns such as the
FastAPI app factory, middleware, settings, error handling, and shared ports. The
`features` package owns business capabilities. The active business capability is
`kanban`.

```text
HTTP client
  -> FastAPI platform app
  -> Kanban inbound HTTP adapter
  -> Kanban application use case
  -> Kanban domain model
  -> outbound port
  -> SQLModel/PostgreSQL adapter
```

## Main Modules

| Module | Responsibility |
| --- | --- |
| `src/main.py` | Builds the FastAPI app, mounts Kanban routes, creates the Kanban container during lifespan startup, and shuts it down during lifespan teardown. |
| `src/platform/api/app_factory.py` | Creates the FastAPI app, configures docs URLs, CORS, trusted hosts, request context middleware, root route, and Problem Details handlers. |
| `src/platform/config/settings.py` | Defines runtime settings loaded from `.env` and environment variables. |
| `src/platform/api/middleware/request_context.py` | Adds or propagates `X-Request-ID` and emits one JSON access log per request. |
| `src/platform/api/error_handlers.py` | Converts framework, validation, dependency, application, and unhandled exceptions into `application/problem+json` responses. |
| `src/features/kanban/domain/` | Contains the pure Kanban model, domain errors, and card movement specifications. |
| `src/features/kanban/application/` | Contains commands, queries, application contracts, ports, and use cases. |
| `src/features/kanban/adapters/inbound/http/` | Contains FastAPI routers, schemas, dependency aliases, mappers, and HTTP error mapping. |
| `src/features/kanban/adapters/outbound/persistence/sqlmodel/` | Contains SQLModel tables, mapping functions, repositories, and unit of work implementation. |
| `src/features/kanban/composition/` | Creates the feature container and wires feature routes and dependencies into the FastAPI app. |
| `alembic/` | Contains migration environment and versioned schema migrations. |

## Layer Boundaries

The architecture is enforced by Import Linter contracts in `pyproject.toml`.

| Boundary | Rule |
| --- | --- |
| Platform isolation | `src.platform` must not import `src.features`. |
| Domain purity | `src.features.kanban.domain` must not import application, adapters, composition, FastAPI, SQLModel, SQLAlchemy, Alembic, Pydantic, or other framework packages. |
| Application isolation | `src.features.kanban.application` must not import adapters, composition, platform API, persistence, FastAPI, SQLModel, SQLAlchemy, Alembic, or other adapter packages. |
| Inbound adapter isolation | `src.features.kanban.adapters.inbound` must not bypass application ports to import outbound adapters or domain directly. |
| Outbound adapter isolation | `src.features.kanban.adapters.outbound` must not import inbound adapters, use cases, or inbound ports. |
| Feature isolation | Feature packages are intended not to import each other. |

Run the boundary checks with:

```bash
make lint-arch
```

## Request Data Flow

1. A request enters the FastAPI app created by `build_fastapi_app()`.
2. `RequestContextMiddleware` stores a request ID on `request.state` and writes
   the same ID to the response header.
3. The platform app dispatches to a route under `/api`, `/auth`, `/admin`, or a
   health endpoint.
4. Inbound dependencies resolve the Kanban container from `app.state`.
5. The route maps Pydantic request schemas into application commands or queries.
6. The route calls a use case through an inbound `Protocol` type alias.
7. The use case coordinates domain objects and outbound ports.
8. Write use cases use `UnitOfWorkPort`; read use cases use `KanbanQueryRepositoryPort`.
9. The SQLModel repository maps SQL rows to domain objects and back.
10. Use cases return `Ok(value)` or `Err(ApplicationError)`.
11. The route maps successful application contracts to Pydantic response schemas.
12. The route raises a feature HTTP exception for application errors.
13. Platform error handlers render Problem Details JSON.

## Domain Model

The Kanban aggregate root is `Board`. A board owns ordered `Column` entities. A
column owns ordered `Card` entities.

Important domain behavior:

- Deleting a column recalculates remaining column positions from zero.
- Inserting, moving, or extracting cards recalculates card positions from zero.
- Moving a card is valid only when the target column exists and belongs to the
  same board.
- Card patching treats omitted fields as unchanged. The `clear_due_at` flag is
  used to distinguish an explicit `null` due date from an omitted due date.

## Persistence Model

PostgreSQL tables are defined with SQLModel:

| Table | Model | Notes |
| --- | --- | --- |
| `boards` | `BoardTable` | Stores `id`, `title`, `version`, and `created_at`. |
| `columns_` | `ColumnTable` | Stores ordered columns. The table name avoids using `columns` as an identifier. |
| `cards` | `CardTable` | Stores ordered cards, priority, optional description, and optional due date. |

The repository saves an entire board aggregate snapshot. Existing columns and
cards that are absent from the current aggregate are deleted. Current columns and
cards are inserted or updated.

`boards.version` is used for optimistic concurrency. A stale aggregate write
raises `PersistenceConflictError`.

Column and card position uniqueness constraints are deferrable and initially
deferred. This allows a reorder operation to make several position updates in one
transaction without failing on temporary duplicate positions before the final
state is committed.

## Application Composition

`create_app()` in `src/main.py` separates route mounting from container startup:

- Routes are mounted when the app object is built so OpenAPI generation and
  routing work before lifespan startup completes.
- The PostgreSQL-backed Kanban container is built during lifespan startup.
- The container is stored on `app.state` and removed during teardown.
- The Kanban repository engine is disposed during shutdown.

## Error Handling

Feature use cases return application errors rather than HTTP exceptions.
`src/features/kanban/adapters/inbound/http/errors.py` maps those application
errors to HTTP status codes and problem type URIs. The platform handler renders
the final response as `application/problem+json`.

Unhandled exceptions are logged through `api.error` with request ID, method,
path, status code, and error type. The client receives a generic `500` Problem
Details response.

## External Services And Dependencies

The application depends on PostgreSQL for runtime persistence. Docker Compose
provides a local `postgres:16-alpine` database. Integration tests use
testcontainers with PostgreSQL when Docker is available.

There are no verified external SaaS integrations in the current source code.

## Design Decisions

| Decision | Reason |
| --- | --- |
| Feature-first layout | Keeps business code, adapters, composition, and tests for a feature close together. |
| Hexagonal boundaries | Keeps domain and application logic independent from FastAPI and SQLModel. |
| Protocol-based ports | Allows tests and adapters to swap implementations without changing use cases. |
| Result type for use cases | Keeps expected business failures explicit without throwing exceptions through application logic. |
| Platform-level Problem Details | Gives all API errors a consistent shape. |
| Read and write routers | Applies API-key protection only to write routes while read routes remain public. |
| Full aggregate save | Keeps column and card ordering logic in the domain model and persists the aggregate snapshot. |
| Deferrable position constraints | Protects final ordering uniqueness while allowing multi-row reorder operations in one transaction. |
| Separate runtime image and migration command | The production image starts only Uvicorn. Docker Compose runs migrations through a one-shot `migrate` service, and production deployments should run migrations as a release step. |

## Tradeoffs And Limitations

- Write protection is a single optional API key, not user authentication or
  authorization.
- Board listing has no pagination.
- There is no endpoint to delete a single card.
- There is no endpoint to rename a column.
- The documented persistence backend is PostgreSQL only.
