## ADDED Requirements

### Requirement: Kanban as canonical feature

The Kanban feature MUST live entirely under `src/features/kanban/` and serve as the reference example for any new feature. No Kanban code MAY live in `src/platform/` or in any other feature.

#### Scenario: Self-contained Kanban
- **WHEN** the entire `src/features/kanban/` directory is removed
- **THEN** the rest of the codebase (platform + main.py + alembic) still imports cleanly
- **AND** only the Kanban routes and Kanban migrations are missing at runtime

### Requirement: Kanban domain content

`src/features/kanban/domain/` MUST contain the aggregate models (`Board`, `Column`, `Card`, `CardPriority`, `BoardSummary`), domain errors (`KanbanError`), and any specifications (e.g., `ValidCardMoveSpecification`). Domain modules MUST NOT import FastAPI, SQLModel, SQLAlchemy, Pydantic, psycopg, or anything from `src.features.kanban.application` or `src.features.kanban.adapters`.

#### Scenario: Domain purity enforced
- **WHEN** `make lint-arch` runs after the migration
- **THEN** the Kanban domain contract passes with zero forbidden imports

### Requirement: Kanban application layer

`src/features/kanban/application/` MUST contain `ports/{inbound,outbound}/`, `commands/`, `queries/`, `contracts/`, `errors.py`, and `use_cases/`. Application modules MUST NOT import FastAPI, SQLModel/SQLAlchemy, Alembic, psycopg, nor any module under `src.features.kanban.adapters`.

#### Scenario: Use cases depend only on ports and domain
- **WHEN** any module under `src/features/kanban/application/use_cases/` is imported
- **THEN** its imports resolve only to `src.features.kanban.application.*`, `src.features.kanban.domain.*`, `src.platform.shared.*`, and stdlib

### Requirement: Kanban HTTP adapter

`src/features/kanban/adapters/inbound/http/` MUST contain the FastAPI routers, Pydantic IO schemas, mappers between schemas and application commands/contracts, and the local Problem+JSON exception class. The router MUST be exposed under prefix `/api` and MUST preserve every path, status code, and payload shape currently served by the legacy routers.

#### Scenario: HTTP surface unchanged after migration
- **WHEN** a request is sent to `POST /api/boards`, `GET /api/boards/{id}`, `POST /api/columns/{column_id}/cards`, or any other current Kanban route
- **THEN** the response status code and body are identical to the pre-refactor behavior

### Requirement: Kanban persistence adapter

`src/features/kanban/adapters/outbound/persistence/sqlmodel/` MUST contain the SQLModel ORM tables, the repository implementing the outbound command and lookup ports, the Unit-of-Work implementing `UnitOfWorkPort`, and the mappers between ORM rows and domain aggregates. Alembic's `target_metadata` MUST resolve to the metadata exposed by this package.

#### Scenario: Alembic upgrade head succeeds after migration
- **WHEN** `uv run alembic upgrade head` runs against a clean PostgreSQL database
- **THEN** all existing migrations apply successfully using the new metadata import path

### Requirement: Kanban composition wiring

`src/features/kanban/composition/wiring.py` MUST expose `register_kanban(app: FastAPI, platform: PlatformContainer) -> None` that builds Kanban's outbound adapters from the platform's engine and includes the Kanban router into the app.

#### Scenario: One-line feature registration
- **WHEN** `src/main.py` calls `register_kanban(app, platform)` during lifespan startup
- **THEN** all Kanban routes are available under `/api/...`
- **AND** the Kanban container is set on `app.state` for dependency lookup
