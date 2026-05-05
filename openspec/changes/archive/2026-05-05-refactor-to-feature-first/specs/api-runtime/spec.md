## ADDED Requirements

### Requirement: Return type drives response serialization

When a path operation's return type is the same Pydantic model used for response serialization, the operation MUST declare only the function return type and MUST NOT also pass `response_model=` on the decorator. The `response_model=` parameter is reserved for cases where the runtime return value differs from the declared response schema.

#### Scenario: Boards endpoint uses return type only
- **WHEN** the migration is complete
- **THEN** `POST /api/boards` declares `def create_board(...) -> BoardSummary` and the decorator omits `response_model=BoardSummary`

### Requirement: Write authentication via router-level dependency

Path operations that mutate state (POST/PATCH/PUT/DELETE) MUST inherit the `require_write_api_key` dependency from a write-only `APIRouter(dependencies=[Depends(require_write_api_key)])`. Read operations (GET) MUST be served by a separate router without that dependency. The same effective behavior MUST be observable: requests without `X-API-Key` matching `APP_WRITE_API_KEY` are rejected with HTTP 401 on writes only.

#### Scenario: Write router enforces key
- **WHEN** the migration is complete and a `POST /api/boards` request arrives without `X-API-Key`
- **THEN** the response is HTTP 401 with Problem+JSON

#### Scenario: Read router does not require key
- **WHEN** a `GET /api/boards/{id}` request arrives without `X-API-Key`
- **THEN** the response is the normal 200/404 result, not 401

#### Scenario: No duplicated `Depends` on individual write operations
- **WHEN** the migration is complete
- **THEN** no path operation decorator under the write router declares `_: WriteApiKeyDep` as a parameter

### Requirement: Single tagging on nested routers

When a parent `APIRouter` includes child routers that already define `tags=[...]`, the parent MUST NOT re-tag them. Each operation MUST appear under exactly one tag in the OpenAPI document.

#### Scenario: Kanban operations not double-tagged
- **WHEN** the OpenAPI document is generated after the migration
- **THEN** every Kanban operation appears under exactly one of `boards`, `columns`, `cards`, `root` and not under `kanban` in addition

### Requirement: FastAPI CLI entrypoint

`pyproject.toml` MUST declare `[tool.fastapi] entrypoint = "src.main:app"`. The dev server MUST be runnable with `fastapi dev` (with reload) and the production server with `fastapi run`. The `make dev` target MUST invoke `fastapi dev`. The `Dockerfile` `CMD` MUST invoke `fastapi run`.

#### Scenario: Dev server starts via fastapi CLI
- **WHEN** a developer runs `fastapi dev`
- **THEN** the API serves on port 8000 with reload enabled

#### Scenario: Container starts via fastapi run
- **WHEN** the Docker image is built and started without overriding the CMD
- **THEN** the API serves on the configured port using `fastapi run`

### Requirement: Typed application settings exposure

The DI container's `settings` attribute exposed via `AppContainer` and the `AppSettingsDep` dependency alias MUST be typed as `AppSettings` (not `Any`). Any code in `src/platform/api/` that depends on settings MUST use the typed alias.

#### Scenario: Mypy passes on settings access
- **WHEN** `make typecheck` runs after the migration
- **THEN** mypy reports zero errors related to settings access in `src/platform/api/`

### Requirement: Container dependency module location

The functions `set_app_container`, `get_app_container`, and `AppContainer` Protocol MUST live in `src/platform/api/dependencies/container.py`. The function `require_write_api_key` and the `WriteApiKeyDep` alias MUST live in `src/platform/api/dependencies/security.py`.

#### Scenario: Module separation
- **WHEN** the migration is complete
- **THEN** `container.py` does not export auth helpers and `security.py` does not export container helpers

### Requirement: Lifespan composition root

`src/main.py` MUST construct a single platform container during the FastAPI lifespan startup and call each feature's `register_<feature>` function exactly once. The lifespan MUST call the platform shutdown hook on teardown.

#### Scenario: Single platform construction
- **WHEN** the API starts
- **THEN** `build_platform(settings)` is called exactly once
- **AND** `register_kanban(app, platform)` is called exactly once

#### Scenario: Clean shutdown
- **WHEN** the API stops
- **THEN** the platform shutdown hook is invoked
- **AND** `app.state.container` is cleared
