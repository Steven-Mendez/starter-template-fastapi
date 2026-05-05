## ADDED Requirements

### Requirement: Domain isolation per feature

For every feature `F`, modules under `src/features/<F>/domain/` MUST NOT import from `src/features/<F>/application/`, `src/features/<F>/adapters/`, `src/platform/api/`, `src/platform/persistence/`, FastAPI, Starlette, SQLModel, SQLAlchemy, Alembic, Uvicorn, HTTPX, Pydantic, Pydantic-Settings, or psycopg.

#### Scenario: Domain contract enforced
- **WHEN** any domain module adds a forbidden import
- **THEN** `make lint-arch` exits non-zero and names the offending module

### Requirement: Application isolation per feature

For every feature `F`, modules under `src/features/<F>/application/` MUST NOT import from `src/features/<F>/adapters/`, `src/platform/api/`, `src/platform/persistence/`, FastAPI, Starlette, SQLModel, SQLAlchemy, Alembic, Uvicorn, HTTPX, Pydantic-Settings, or psycopg. Pydantic itself is allowed for DTOs.

#### Scenario: Application stays framework-agnostic
- **WHEN** `make lint-arch` runs
- **THEN** application modules importing forbidden modules are reported

### Requirement: Adapter layering per feature

For every feature `F`, modules under `src/features/<F>/adapters/inbound/` MUST NOT import from `src/features/<F>/adapters/outbound/`, and modules under `src/features/<F>/adapters/outbound/` MUST NOT import from `src/features/<F>/adapters/inbound/` nor from `src/features/<F>/application/use_cases/` nor from `src/features/<F>/application/ports/inbound/`.

#### Scenario: Inbound and outbound adapters do not couple
- **WHEN** `make lint-arch` runs
- **THEN** no adapter cross-import contract is violated

### Requirement: Cross-feature isolation

For any two distinct features `F` and `G`, modules under `src/features/<F>/` MUST NOT import any module under `src/features/<G>/`.

#### Scenario: Adding a second feature
- **WHEN** a future feature `users` is added and accidentally imports `src.features.kanban.domain.models.board`
- **THEN** `make lint-arch` fails with a cross-feature violation

### Requirement: Platform isolation

Modules under `src/platform/` MUST NOT import from `src/features/`.

#### Scenario: Platform never depends on features
- **WHEN** `make lint-arch` runs
- **THEN** zero `src.platform.* -> src.features.*` imports are detected

### Requirement: Global inward direction

The dependency direction `src.features.*.adapters → src.features.*.application → src.features.*.domain` MUST be enforced as a layered contract.

#### Scenario: Layer contract enforced
- **WHEN** any reverse import is introduced (e.g., a domain module imports an application module)
- **THEN** `make lint-arch` reports the layering violation
