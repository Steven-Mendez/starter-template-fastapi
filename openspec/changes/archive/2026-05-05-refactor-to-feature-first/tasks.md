## 1. Pre-flight

- [x] 1.1 Confirm `make check` is green on the current `main`
- [x] 1.2 Create a feature branch `refactor/feature-first`
- [x] 1.3 Snapshot current OpenAPI (`curl http://localhost:8000/openapi.json > /tmp/openapi-before.json`) for diffing later

## 2. Platform package

- [x] 2.1 Create `src/platform/` with `__init__.py` and the subpackages `config/`, `api/`, `persistence/`, `shared/`, `shared/adapters/`
- [x] 2.2 Move `src/infrastructure/config/settings.py` to `src/platform/config/settings.py` and update its imports
- [x] 2.3 Move `src/domain/shared/result.py` to `src/platform/shared/result.py`
- [x] 2.4 Move `src/application/ports/clock_port.py` and `id_generator_port.py` to `src/platform/shared/`
- [x] 2.5 Move `src/infrastructure/adapters/outbound/clock/system_clock.py` and `id_generator/uuid_id_generator.py` to `src/platform/shared/adapters/`
- [x] 2.6 Create `src/platform/persistence/sqlmodel/engine.py` with `build_engine(settings)` extracted from current composition
- [x] 2.7 Move `src/infrastructure/adapters/outbound/persistence/lifecycle.py` to `src/platform/persistence/`
- [x] 2.8 Move `src/application/shared/readiness.py` to `src/platform/persistence/readiness.py`
- [x] 2.9 Move `src/api/error_handlers.py` to `src/platform/api/error_handlers.py`
- [x] 2.10 Move the request_context middleware out of `src/main.py` into `src/platform/api/middleware/request_context.py` (BaseHTTPMiddleware class)
- [x] 2.11 Move `set_app_container`/`get_app_container`/`AppContainer` Protocol into `src/platform/api/dependencies/container.py`
- [x] 2.12 Move `require_write_api_key`/`WriteApiKeyDep` into `src/platform/api/dependencies/security.py` (no container helpers here)
- [x] 2.13 Type `AppContainer.settings` and `AppSettingsDep` as `AppSettings` (eliminate `Any`)
- [x] 2.14 Create `src/platform/api/app_factory.py` exposing `build_fastapi_app(settings, platform)` that wires CORS, TrustedHost, error handlers and middleware
- [x] 2.15 Create `src/platform/__init__.py` exporting `build_platform`, `PlatformContainer`, `build_fastapi_app`

## 3. Kanban domain

- [x] 3.1 Create `src/features/kanban/` with `__init__.py`
- [x] 3.2 `git mv src/domain/kanban src/features/kanban/domain`
- [x] 3.3 Update domain imports: `src.domain.shared.result` → `src.platform.shared.result`
- [x] 3.4 Run `make lint-arch typecheck` (contracts likely fail until step 7; mypy must pass)

## 4. Kanban application

- [x] 4.1 Move `src/application/ports/kanban_*.py` and `unit_of_work_port.py` to `src/features/kanban/application/ports/outbound/`
- [x] 4.2 Move `src/application/contracts/` to `src/features/kanban/application/contracts/`
- [x] 4.3 Move `src/application/commands/` to `src/features/kanban/application/commands/`
- [x] 4.4 Move `src/application/queries/` to `src/features/kanban/application/queries/`
- [x] 4.5 Move `src/application/kanban/errors.py` to `src/features/kanban/application/errors.py`
- [x] 4.6 Move `src/application/use_cases/` to `src/features/kanban/application/use_cases/`
- [x] 4.7 Update all internal imports inside the moved modules to the new paths
- [x] 4.8 Create one inbound Protocol per use case under `src/features/kanban/application/ports/inbound/` (`create_board.py`, `patch_board.py`, `delete_board.py`, `get_board.py`, `list_boards.py`, `create_column.py`, `delete_column.py`, `create_card.py`, `patch_card.py`, `get_card.py`, `check_readiness.py`)
- [x] 4.9 Run `make typecheck`

## 5. Kanban adapters

- [x] 5.1 Move `src/infrastructure/adapters/outbound/persistence/sqlmodel/` to `src/features/kanban/adapters/outbound/persistence/sqlmodel/`
- [x] 5.2 Move `src/infrastructure/adapters/outbound/query/kanban_query_repository_view.py` to `src/features/kanban/adapters/outbound/query/`
- [x] 5.3 Move `src/api/routers/{boards,columns,cards,health,_errors}.py` to `src/features/kanban/adapters/inbound/http/`
- [x] 5.4 Move `src/api/schemas/` to `src/features/kanban/adapters/inbound/http/schemas/`
- [x] 5.5 Move `src/api/mappers/kanban/` to `src/features/kanban/adapters/inbound/http/mappers/`
- [x] 5.6 Move `src/api/dependencies/use_cases.py` into `src/features/kanban/adapters/inbound/http/dependencies.py` and retype its parameters using inbound Protocols
- [x] 5.7 Apply FastAPI cleanup: remove `response_model=` where redundant on every Kanban operation
- [x] 5.8 Split each router into `_read_router` and `_write_router`; the write router is `APIRouter(dependencies=[Depends(require_write_api_key)])`; remove `_: WriteApiKeyDep` parameters from individual operations
- [x] 5.9 Remove `tags=["kanban"]` from the parent `kanban_router` (children already tag themselves)
- [x] 5.10 Move `src/api/routers/root.py` content into `src/platform/api/` if it serves only the platform-level routes, or keep with Kanban's `health.py` if it is feature-bound

## 6. Composition

- [x] 6.1 Create `src/features/kanban/composition/container.py` with `KanbanContainer` (use case factories + outbound adapter wiring)
- [x] 6.2 Create `src/features/kanban/composition/wiring.py` exposing `register_kanban(app, platform)` that builds the Kanban container and includes its router
- [x] 6.3 Reduce `src/main.py` to: `build_platform(settings)` → `build_fastapi_app(settings, platform)` → `register_kanban(app, platform)` inside lifespan
- [x] 6.4 Run the API locally (`fastapi dev` once step 8 is done, otherwise `uvicorn src.main:app`) and curl-smoke `/health`, `POST /api/boards`, `GET /api/boards`, `POST /api/columns/{id}/cards`

## 7. Import-linter rewrite

- [x] 7.1 Remove the legacy global contracts (Domain/Application/API/Infrastructure layered) from `pyproject.toml`
- [x] 7.2 Add per-feature contracts for Kanban: domain isolation, application isolation, adapter inbound/outbound layering
- [x] 7.3 Add platform isolation contract (`src.platform` cannot import `src.features.*`)
- [x] 7.4 Add cross-feature isolation contract template (placeholder ready for future features)
- [x] 7.5 Add global layered contract: `src.features.*.adapters → src.features.*.application → src.features.*.domain`
- [x] 7.6 Run `make lint-arch` and fix every reported violation by adjusting imports (no contract softening)

## 8. FastAPI CLI + Docker

- [x] 8.1 Add `[tool.fastapi] entrypoint = "src.main:app"` to `pyproject.toml`
- [x] 8.2 Update `Makefile` `dev` target to `uv run fastapi dev`
- [x] 8.3 Update `Dockerfile` `CMD` to `["uv", "run", "fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]`
- [x] 8.4 Smoke-test: `make dev`, then curl `/health`

## 9. Alembic

- [x] 9.1 Update `alembic/env.py` to import `target_metadata` from the new path (`src.features.kanban.adapters.outbound.persistence.sqlmodel.models.metadata`)
- [x] 9.2 Run `uv run alembic upgrade head` against a clean local database; verify it succeeds
- [x] 9.3 Run `uv run alembic check` (or autogenerate dry-run) to confirm metadata import is wired correctly

## 10. Cleanup

- [x] 10.1 Delete the now-empty legacy directories: `src/api/`, `src/application/`, `src/domain/`, `src/infrastructure/`, `src/config/`
- [x] 10.2 Update `README.md` "Quick start" and "Project layout" sections to reflect feature-first paths
- [x] 10.3 Add a brief "Migration from layer-first" subsection in `README.md`
- [x] 10.4 Run the full quality gate: `make check` (lint + lint-arch + typecheck) — must be green
- [x] 10.5 Diff `/openapi.json` against the snapshot from 1.3 and confirm only path tags / response_model annotations differ — no path or status code regressions

## 11. Verification

- [x] 11.1 `make check` green
- [x] 11.2 `uv run alembic upgrade head` green against a fresh DB
- [x] 11.3 Manual smoke test of each Kanban operation (`POST/GET/PATCH/DELETE` boards, columns, cards) returns the same shapes as before the refactor
- [x] 11.4 OpenAPI shows each Kanban operation under exactly one tag (no `kanban` duplication)
- [x] 11.5 `POST/PATCH/DELETE /api/boards` rejects with HTTP 401 when `X-API-Key` is missing and `APP_WRITE_API_KEY` is set
